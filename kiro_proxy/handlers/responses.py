"""OpenAI Responses API 处理 - /v1/responses

Codex CLI 使用的 API 端点，深度适配 Codex 源码
"""
import json
import uuid
import time
import asyncio
import os
import re
import httpx
from typing import Any, Dict, Optional, Tuple
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse

from ..config import KIRO_API_URL, map_model_name
from ..core import state, is_retryable_error, stats_manager
from ..core.state import RequestLog
from ..core.history_manager import HistoryManager, get_history_config
from ..core.error_handler import classify_error, ErrorType, format_error_log
from ..core.rate_limiter import get_rate_limiter
from ..core.auth_guard import ensure_profile_arn_ready
from ..http_client import get_httpx_verify_setting, create_async_client
from ..kiro_api import build_headers, build_kiro_request, parse_event_stream, parse_event_stream_full, is_quota_exceeded_error


_DEBUG_RESPONSES = os.getenv("KIRO_PROXY_DEBUG_RESPONSES", "").lower() in {"1", "true", "yes", "on"}
_TOOL_CALL_TYPES = {"function_call", "custom_tool_call", "local_shell_call", "tool_search_call"}
_TOOL_OUTPUT_TYPES = {"function_call_output", "custom_tool_call_output", "mcp_tool_call_output", "tool_search_output"}
_SPECIAL_ASSISTANT_CALL_TYPES = {"web_search_call", "image_generation_call"}


def _debug(message: str):
    if _DEBUG_RESPONSES:
        print(message)


def _parse_data_image(image_url: str) -> Optional[dict]:
    if not isinstance(image_url, str) or not image_url.startswith("data:"):
        return None
    match = re.match(r"data:image/([\w.+-]+);base64,(.+)", image_url)
    if not match:
        return None
    return {
        "format": match.group(1).lower(),
        "source": {"bytes": match.group(2)}
    }


def _extract_text_and_images_from_message_content(content: Any) -> Tuple[str, list]:
    if isinstance(content, str):
        return content, []

    blocks = content if isinstance(content, list) else [content]
    text_parts = []
    images = []

    for block in blocks:
        if isinstance(block, str):
            if block:
                text_parts.append(block)
            continue

        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "")
        if block_type in {"input_text", "output_text", "text", "summary_text", "reasoning_text"}:
            text = block.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)
            continue

        if block_type == "input_image":
            image_url = block.get("image_url", "")
            if isinstance(image_url, dict):
                image_url = image_url.get("url", "")
            parsed = _parse_data_image(image_url)
            if parsed:
                images.append(parsed)
            continue

        # 兼容 mcp output 里的 text block
        text = block.get("text")
        if isinstance(text, str) and text:
            text_parts.append(text)

    return "\n".join(text_parts), images


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _extract_tool_output_text(output: Any) -> str:
    if output is None:
        return ""

    if isinstance(output, str):
        return output

    if isinstance(output, list):
        text, _ = _extract_text_and_images_from_message_content(output)
        return text if text else _safe_json_dumps(output)

    if isinstance(output, dict):
        if isinstance(output.get("content"), str):
            return output["content"]
        if isinstance(output.get("content"), list):
            content_text, _ = _extract_text_and_images_from_message_content(output["content"])
            if content_text:
                return content_text
        if isinstance(output.get("text"), str):
            return output["text"]
        if "result" in output and isinstance(output["result"], (str, int, float, bool)):
            return str(output["result"])
        return _safe_json_dumps(output)

    return str(output)


def _parse_tool_output(item: dict) -> Optional[dict]:
    call_id = item.get("call_id") or item.get("id")
    if not call_id:
        _debug(f"[Responses] Skip tool output without call_id: type={item.get('type')}")
        return None

    output = item.get("output")
    if output is None and item.get("type") == "tool_search_output":
        output = {
            "status": item.get("status"),
            "execution": item.get("execution"),
            "tools": item.get("tools", []),
        }

    status = "success"
    status_raw = str(item.get("status", "")).lower()
    if status_raw in {"error", "failed", "failure", "cancelled", "canceled"}:
        status = "error"

    if isinstance(output, dict):
        if output.get("success") is False or output.get("is_error") is True or output.get("isError") is True:
            status = "error"

    output_text = _extract_tool_output_text(output)
    if not output_text:
        output_text = "Tool execution completed."

    return {
        "content": [{"text": output_text}],
        "status": status,
        "toolUseId": str(call_id),
    }


def _parse_tool_call(item: dict) -> Optional[dict]:
    item_type = item.get("type", "")
    call_id = item.get("call_id") or item.get("id")
    if not call_id:
        _debug(f"[Responses] Skip tool call without call_id: type={item_type}")
        return None

    name = item.get("name") or item_type
    tool_input: Dict[str, Any] = {}

    if item_type == "function_call":
        namespace = item.get("namespace")
        if isinstance(namespace, str) and namespace.strip():
            name = f"{namespace.strip()}.{name}"
        arguments = item.get("arguments", {})
        if isinstance(arguments, str):
            try:
                tool_input = json.loads(arguments)
            except Exception:
                tool_input = {"raw_arguments": arguments}
        elif isinstance(arguments, dict):
            tool_input = arguments
        else:
            tool_input = {"raw_arguments": str(arguments)}

    elif item_type == "custom_tool_call":
        raw_input = item.get("input", "")
        if isinstance(raw_input, dict):
            tool_input = raw_input
        elif isinstance(raw_input, str):
            tool_input = {"input": raw_input}
        else:
            tool_input = {"input": str(raw_input)}

    elif item_type == "local_shell_call":
        name = "local_shell"
        action = item.get("action", {})
        if isinstance(action, dict):
            tool_input = action
        elif action:
            tool_input = {"action": action}

    elif item_type == "tool_search_call":
        name = "tool_search"
        arguments = item.get("arguments", {})
        if isinstance(arguments, dict):
            tool_input = arguments
        elif isinstance(arguments, str):
            try:
                tool_input = json.loads(arguments)
            except Exception:
                tool_input = {"query": arguments}
        else:
            tool_input = {"query": str(arguments)}

        execution = item.get("execution")
        if execution and "execution" not in tool_input:
            tool_input["execution"] = execution

    if not isinstance(tool_input, dict):
        tool_input = {"input": str(tool_input)}

    return {
        "toolUseId": str(call_id),
        "name": str(name),
        "input": tool_input,
    }


def _summarize_special_assistant_call(item: dict) -> str:
    item_type = item.get("type", "")
    status = str(item.get("status") or "completed")

    if item_type == "web_search_call":
        action = item.get("action", {})
        if not isinstance(action, dict):
            action = {}
        action_type = str(action.get("type") or "search")
        query = str(action.get("query") or "").strip()
        if query:
            return f"[web_search_call:{status}] {action_type}: {query}"
        return f"[web_search_call:{status}] {action_type}"

    if item_type == "image_generation_call":
        revised_prompt = str(item.get("revised_prompt") or "").strip()
        result = item.get("result")
        result_note = ""
        if isinstance(result, str) and result.startswith("data:image/"):
            result_note = "result=data_image"
        elif result:
            result_note = "result=present"

        parts = [f"[image_generation_call:{status}]"]
        if revised_prompt:
            parts.append(f"prompt={revised_prompt}")
        if result_note:
            parts.append(result_note)
        return " ".join(parts)

    return ""


def _convert_responses_input_to_kiro(input_data, instructions: str = None):
    """将 Responses API 的 input 转换为 Kiro 格式
    
    Codex 发送的 input 格式:
    - message (role=user): 用户消息
    - message (role=assistant): 助手回复
    - function_call: 工具调用
    - function_call_output: 工具调用结果
    
    Kiro API 期望的格式:
    - history: [userInputMessage, assistantResponseMessage, ...] 交替
    - 当 assistant 有 toolUses 时，下一条 userInputMessage 必须包含对应的 toolResults
    - 当前请求的 userInputMessage 只包含最新一轮的 toolResults
    """
    history = []
    user_content = ""
    tool_results = []
    model_id = "claude-sonnet-4"
    first_user_msg_added = False
    pending_images = []
    
    if isinstance(input_data, str):
        if instructions:
            return f"{instructions}\n\n{input_data}", history, tool_results, None
        return input_data, history, tool_results, None
    
    if not isinstance(input_data, list):
        return user_content, history, tool_results, None
    
    # 线性处理消息，跟踪状态
    pending_user_texts = []
    pending_tool_uses = []
    pending_tool_outputs = []

    def _flush_pending_tool_uses(default_content: str = "I will use available tools."):
        nonlocal pending_tool_uses
        if not pending_tool_uses:
            return
        if history and "assistantResponseMessage" in history[-1]:
            history[-1]["assistantResponseMessage"].setdefault("toolUses", []).extend(pending_tool_uses)
        else:
            history.append({
                "assistantResponseMessage": {
                    "content": default_content,
                    "toolUses": pending_tool_uses
                }
            })
        pending_tool_uses = []

    def _flush_pending_user():
        nonlocal pending_user_texts, pending_tool_outputs, first_user_msg_added
        if pending_user_texts:
            combined_user = "\n\n".join(pending_user_texts)
            if not first_user_msg_added and instructions:
                combined_user = f"{instructions}\n\n{combined_user}"
                first_user_msg_added = True

            user_msg = {
                "userInputMessage": {
                    "content": combined_user,
                    "modelId": model_id,
                    "origin": "AI_EDITOR"
                }
            }
            if pending_tool_outputs:
                _flush_pending_tool_uses()
                user_msg["userInputMessage"]["userInputMessageContext"] = {
                    "toolResults": pending_tool_outputs
                }
                pending_tool_outputs = []

            history.append(user_msg)
            pending_user_texts = []
            return

        if pending_tool_outputs:
            _flush_pending_tool_uses()
            history.append({
                "userInputMessage": {
                    "content": "Tool execution completed.",
                    "modelId": model_id,
                    "origin": "AI_EDITOR",
                    "userInputMessageContext": {
                        "toolResults": pending_tool_outputs
                    }
                }
            })
            pending_tool_outputs = []
    
    for item in input_data:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type", "")
        
        if item_type == "message":
            role = item.get("role", "user")
            text, images = _extract_text_and_images_from_message_content(item.get("content", []))
            
            if role == "user":
                if images:
                    pending_images.extend(images)
                pending_user_texts.append(text)
            
            elif role == "assistant":
                # 遇到 assistant 消息，先处理之前的 user/tool output
                _flush_pending_user()
                
                # 添加 assistant 消息
                assistant_msg = {
                    "assistantResponseMessage": {
                        "content": text or "I understand."
                    }
                }
                if pending_tool_uses:
                    assistant_msg["assistantResponseMessage"]["toolUses"] = pending_tool_uses
                    pending_tool_uses = []
                
                history.append(assistant_msg)

        elif item_type in _SPECIAL_ASSISTANT_CALL_TYPES:
            summary = _summarize_special_assistant_call(item)
            if not summary:
                continue
            _flush_pending_user()
            _flush_pending_tool_uses()
            history.append({
                "assistantResponseMessage": {
                    "content": summary
                }
            })
        
        elif item_type in _TOOL_CALL_TYPES:
            tool_use = _parse_tool_call(item)
            if not tool_use:
                continue

            # 如果上一条是 assistant 消息，添加 toolUses
            if history and "assistantResponseMessage" in history[-1]:
                history[-1]["assistantResponseMessage"].setdefault("toolUses", []).append(tool_use)
            else:
                pending_tool_uses.append(tool_use)
        
        elif item_type in _TOOL_OUTPUT_TYPES:
            tool_output = _parse_tool_output(item)
            if tool_output:
                pending_tool_outputs.append(tool_output)
    
    # 处理剩余的消息
    if pending_tool_outputs:
        _flush_pending_tool_uses()

    if pending_user_texts:
        user_content = "\n\n".join([t for t in pending_user_texts if t])
        if not first_user_msg_added and instructions:
            user_content = f"{instructions}\n\n{user_content}" if user_content else instructions
    elif pending_tool_outputs:
        user_content = "Please continue based on the tool results."
    
    if pending_tool_outputs:
        tool_results = pending_tool_outputs
    
    # 验证并修复 history 中的 toolUses/toolResults 配对
    # Kiro API 规则：当 assistant 有 toolUses 时，下一条 user 必须有对应的 toolResults
    for i in range(len(history) - 1):
        if "assistantResponseMessage" in history[i]:
            assistant = history[i]["assistantResponseMessage"]
            has_tool_uses = bool(assistant.get("toolUses"))
            
            if i + 1 < len(history) and "userInputMessage" in history[i + 1]:
                user = history[i + 1]["userInputMessage"]
                ctx = user.get("userInputMessageContext", {})
                has_tool_results = bool(ctx.get("toolResults"))
                
                # 确保配对一致
                if has_tool_uses and not has_tool_results:
                    # assistant 有 toolUses 但 user 没有 toolResults，清除 toolUses
                    _debug(f"[Responses] history[{i}] has toolUses but history[{i + 1}] has no toolResults, removing toolUses")
                    assistant.pop("toolUses", None)
                elif not has_tool_uses and has_tool_results:
                    # assistant 没有 toolUses 但 user 有 toolResults，清除 toolResults
                    _debug(f"[Responses] history[{i}] has no toolUses but history[{i + 1}] has toolResults, removing toolResults")
                    user.pop("userInputMessageContext", None)
    
    _debug(f"[Responses] Converted: history={len(history)}, tool_results={len(tool_results)}, images={len(pending_images)}")
    
    images = pending_images if pending_images else None
    return user_content, history, tool_results, images


def _convert_tools_to_kiro(tools: list) -> list:
    """将 Responses API 的 tools 转换为 Kiro 格式
    
    Codex Responses API 工具格式:
    {
        "type": "function",
        "name": "...",
        "description": "...",
        "strict": true,
        "parameters": {...}
    }
    
    或特殊工具:
    {
        "type": "web_search",
        "external_web_access": true/false
    }
    {
        "type": "local_shell"
    }
    
    Kiro API 期望的格式:
    {
        "toolSpecification": {
            "name": "...",
            "description": "...",
            "inputSchema": {"json": {...}}
        }
    }
    或
    {
        "webSearchTool": {"type": "web_search"}
    }
    """
    if not tools:
        return None
    
    MAX_TOOLS = 50  # Kiro API 工具数量限制
    MAX_DESCRIPTION_LENGTH = 9216
    kiro_tools = []
    function_count = 0

    def add_tool_spec(name: str, description: str, parameters: dict):
        nonlocal function_count
        if function_count >= MAX_TOOLS or not name:
            return
        function_count += 1
        kiro_tools.append({
                "toolSpecification": {
                    "name": name,
                    "description": (description or f"Tool: {name}")[:MAX_DESCRIPTION_LENGTH],
                    "inputSchema": {"json": parameters or {"type": "object", "properties": {}}}
                }
            })
    
    for tool in tools:
        tool_type = tool.get("type", "")
        
        # 特殊工具类型
        if tool_type in {"web_search", "web_search_preview"}:
            # external_web_access=false 明确关闭联网时，不向 Kiro 暴露 web_search
            if tool.get("external_web_access") is False:
                continue
            kiro_tools.append({
                "webSearchTool": {
                    "type": "web_search"
                }
            })
            continue

        if tool_type == "local_shell":
            # 将 local_shell 降级映射为普通函数工具，保留命令执行能力
            add_tool_spec(
                "local_shell",
                tool.get("description", "Execute shell commands in a controlled environment."),
                {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Command tokens, e.g. [\"ls\", \"-la\"]"
                        },
                        "workdir": {"type": "string"},
                        "timeout_ms": {"type": "integer", "minimum": 1},
                        "justification": {"type": "string"},
                        "sandbox_permissions": {"type": "string"},
                    },
                    "required": ["command"]
                }
            )
            continue

        if tool_type == "tool_search":
            add_tool_spec(
                "tool_search",
                tool.get("description", "Search available tools."),
                tool.get("parameters", {"type": "object", "properties": {"query": {"type": "string"}}})
            )
            continue

        if tool_type == "image_generation":
            add_tool_spec(
                "image_generation",
                tool.get("description", "Generate an image from prompt text."),
                {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "size": {"type": "string"},
                        "output_format": {"type": "string"},
                    },
                    "required": ["prompt"]
                }
            )
            continue
        
        # 限制工具数量
        if function_count >= MAX_TOOLS:
            continue
        
        # Responses API 格式：字段直接在工具对象上
        # Chat Completions API 格式：字段嵌套在 function 里
        if tool_type == "function":
            # 检查是否是 Chat Completions 格式（有 function 嵌套）
            if "function" in tool:
                func = tool["function"]
                name = func.get("name", "")
                description = func.get("description", "")[:MAX_DESCRIPTION_LENGTH]
                parameters = func.get("parameters", {"type": "object", "properties": {}})
            else:
                # Responses API 格式
                name = tool.get("name", "")
                description = tool.get("description", "")[:MAX_DESCRIPTION_LENGTH]
                parameters = tool.get("parameters", {"type": "object", "properties": {}})
        elif tool_type == "custom":
            # 自定义工具格式
            name = tool.get("name", "")
            description = tool.get("description", "")[:MAX_DESCRIPTION_LENGTH]
            # custom 工具可能有不同的 schema 格式
            fmt = tool.get("format", {})
            if fmt.get("type") == "json_schema":
                parameters = fmt.get("schema", {"type": "object", "properties": {}})
            else:
                parameters = {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                    "required": ["input"]
                }
        else:
            name = tool.get("name", "") or tool_type
            description = tool.get("description", "")[:MAX_DESCRIPTION_LENGTH]
            parameters = tool.get("parameters", tool.get("input_schema", {"type": "object", "properties": {}}))
        
        add_tool_spec(name, description, parameters)
    
    return kiro_tools if kiro_tools else None


async def handle_responses(request: Request):
    """处理 /v1/responses 请求"""
    start_time = time.time()
    log_id = uuid.uuid4().hex[:12]
    
    body = await request.json()
    model = map_model_name(body.get("model", "gpt-4o"))
    input_data = body.get("input", "")
    instructions = body.get("instructions", "")
    stream = body.get("stream", True)
    tools = body.get("tools", [])
    
    if not input_data:
        raise HTTPException(400, "input required")
    
    import hashlib
    session_str = json.dumps(input_data[:3] if isinstance(input_data, list) else str(input_data)[:100], sort_keys=True, default=str)
    session_id = hashlib.sha256(session_str.encode()).hexdigest()[:16]
    account = state.get_available_account(session_id)
    
    if not account:
        raise HTTPException(503, "All accounts are rate limited or unavailable")
    
    if account.is_token_expiring_soon(5):
        await account.refresh_token()
    
    token = account.get_token()
    if not token:
        raise HTTPException(500, f"Failed to get token for account {account.name}")
    
    profile_ok, profile_msg = await ensure_profile_arn_ready(account)
    if not profile_ok:
        raise HTTPException(401, profile_msg)
    
    token = account.get_token()
    
    creds = account.get_credentials()
    headers = build_headers(
        token,
        machine_id=account.get_machine_id(),
        profile_arn=creds.profile_arn if creds else None,
        client_id=creds.client_id if creds else None,
        uuid=getattr(creds, "uuid", None) if creds else None,
    )
    
    rate_limiter = get_rate_limiter()
    can_request, wait_seconds, _ = rate_limiter.can_request(account.id)
    if not can_request:
        await asyncio.sleep(wait_seconds)
    
    user_content, history, tool_results, images = _convert_responses_input_to_kiro(input_data, instructions)
    
    # 修复历史消息交替
    from ..converters import fix_history_alternation
    history = fix_history_alternation(history)
    
    history_manager = HistoryManager(get_history_config(), cache_key=session_id)
    
    # 获取账号凭证
    creds = account.get_credentials()
    
    # 对于 Responses API，强制启用自动截断（Codex CLI 的历史可能很长）
    from ..core.history_manager import TruncateStrategy
    if TruncateStrategy.AUTO_TRUNCATE not in history_manager.config.strategies:
        history_manager.config.strategies.append(TruncateStrategy.AUTO_TRUNCATE)
    
    # 创建摘要 API 调用函数
    async def api_caller(prompt: str) -> str:
        req = build_kiro_request(prompt, "claude-haiku-4.5", [], credentials=creds)
        try:
            async with create_async_client(timeout=60, account_proxy_url=account.get_proxy_url()) as client:
                resp = await client.post(KIRO_API_URL, json=req, headers=headers)
                if resp.status_code == 200:
                    return parse_event_stream(resp.content)
        except Exception as e:
            print(f"[Responses] Summary API 调用失败: {e}")
        return ""
    
    # 检查是否需要智能摘要或错误重试预摘要
    if history_manager.should_summarize(history) or history_manager.should_pre_summary_for_error_retry(history, user_content):
        history = await history_manager.pre_process_async(history, user_content, api_caller)
    else:
        history = history_manager.pre_process(history, user_content)
    
    # 摘要/截断后再次修复历史交替和 toolUses/toolResults 配对
    history = fix_history_alternation(history)
    
    if history_manager.was_truncated:
        print(f"[Responses] {history_manager.truncate_info}")
    
    kiro_tools = _convert_tools_to_kiro(tools)
    
    # 调试：打印 input 结构
    if _DEBUG_RESPONSES and isinstance(input_data, list):
        for i, item in enumerate(input_data):
            item_type = item.get("type", "?")
            role = item.get("role", "?")
            _debug(f"[Responses] input[{i}]: type={item_type}, role={role}")
        _debug(f"[Responses] history len={len(history)}, tool_results={len(tool_results)}, images={len(images) if images else 0}")
        _debug(f"[Responses] user_content len={len(user_content)}")
    
    # 验证 tool_results 与 history 的一致性
    if tool_results and history:
        # 从末尾向前找“最近一个包含 toolUses 的 assistant”。
        # Codex 可能在 tool call 之后追加 web_search_call/image_generation_call，
        # 这些 assistant 条目没有 toolUses，不应导致 tool_results 被误清空。
        last_assistant_idx = -1
        last_assistant = None
        last_assistant_with_tools_idx = -1
        last_assistant_with_tools = None

        for i, msg in enumerate(reversed(history)):
            if "assistantResponseMessage" not in msg:
                continue
            assistant_msg = msg["assistantResponseMessage"]
            idx = len(history) - 1 - i
            if last_assistant is None:
                last_assistant = assistant_msg
                last_assistant_idx = idx
            if assistant_msg.get("toolUses"):
                last_assistant_with_tools = assistant_msg
                last_assistant_with_tools_idx = idx
                break

        target_assistant = last_assistant_with_tools or last_assistant
        target_idx = last_assistant_with_tools_idx if last_assistant_with_tools else last_assistant_idx

        if target_assistant:
            tool_use_ids = set()
            for tu in target_assistant.get("toolUses", []) or []:
                tu_id = tu.get("toolUseId")
                if tu_id:
                    tool_use_ids.add(tu_id)

            _debug(f"[Responses] Target assistant idx={target_idx}, toolUse_ids={tool_use_ids}")
            _debug(f"[Responses] tool_results ids={[tr.get('toolUseId') for tr in tool_results]}")

            if tool_use_ids:
                filtered_results = [tr for tr in tool_results if tr.get("toolUseId") in tool_use_ids]
                if len(filtered_results) != len(tool_results):
                    _debug(f"[Responses] Filtered tool_results: {len(tool_results)} -> {len(filtered_results)}")
                tool_results = filtered_results
            else:
                _debug("[Responses] No assistant with toolUses for current tool_results, clearing")
                tool_results = []
        else:
            _debug("[Responses] No assistant message in history, clearing tool_results")
            tool_results = []
    
    # 确保所有消息都有非空的 content
    for i, msg in enumerate(history):
        if "userInputMessage" in msg:
            uim = msg["userInputMessage"]
            if not uim.get("content"):
                uim["content"] = "Continue"
        elif "assistantResponseMessage" in msg:
            arm = msg["assistantResponseMessage"]
            if not arm.get("content"):
                arm["content"] = "I understand."
    
    kiro_request = build_kiro_request(
        user_content, model, history,
        tools=kiro_tools,
        images=images,
        tool_results=tool_results if tool_results else None,
        credentials=creds
    )
    
    # 调试：打印完整的 Kiro 请求（使用深拷贝避免修改原始请求）
    if tool_results and _DEBUG_RESPONSES:
        import copy
        # 打印请求结构（不包括 tools，因为太长）
        debug_request = copy.deepcopy({
            "conversationState": {
                "history_len": len(kiro_request.get("conversationState", {}).get("history", [])),
                "currentMessage": kiro_request.get("conversationState", {}).get("currentMessage", {}),
            }
        })
        # 移除 tools 以便打印（只在 debug_request 中）
        if "userInputMessageContext" in debug_request["conversationState"]["currentMessage"].get("userInputMessage", {}):
            ctx = debug_request["conversationState"]["currentMessage"]["userInputMessage"]["userInputMessageContext"]
            if "tools" in ctx:
                ctx["tools_count"] = len(ctx["tools"])
                del ctx["tools"]
        _debug(f"[Responses] Kiro request structure: {json.dumps(debug_request, indent=2)}")
    
    if stream:
        return await _handle_stream(kiro_request, headers, account, model, log_id, start_time)
    
    # 非流式
    async with create_async_client(timeout=120, account_proxy_url=account.get_proxy_url()) as client:
        resp = await client.post(KIRO_API_URL, json=kiro_request, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)
        
        result = parse_event_stream_full(resp.content)
        account.request_count += 1
        account.last_used = time.time()
        get_rate_limiter().record_request(account.id)
        
        return _build_response(result, model, log_id)


def _build_response(result: dict, model: str, response_id: str) -> dict:
    """构建非流式响应"""
    text = "".join(result.get("content", []))
    output = []
    
    if text:
        output.append({
            "type": "message",
            "id": f"msg_{response_id}",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text, "annotations": []}]
        })
    
    for tool_use in result.get("tool_uses", []):
        call_id = tool_use.get("id") or f"call_{uuid.uuid4().hex[:12]}"
        output.append({
            "type": "function_call",
            "id": call_id,
            "call_id": call_id,
            "name": tool_use.get("name", ""),
            "arguments": json.dumps(tool_use.get("input", {}))
        })
    
    return {
        "id": f"resp_{response_id}",
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": model,
        "output": output,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    }


async def _handle_stream(kiro_request, headers, account, model, log_id, start_time):
    """流式处理 - Codex 期望的 SSE 格式"""
    
    if _DEBUG_RESPONSES:
        debug_dir = "debug_requests"
        os.makedirs(debug_dir, exist_ok=True)
        debug_file = f"{debug_dir}/{log_id}_request.json"
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(kiro_request, f, indent=2, ensure_ascii=False)
        _debug(f"[Responses] Saved request to {debug_file}")
    
    async def generate():
        response_id = f"resp_{log_id}"
        item_id = f"msg_{log_id}"
        created_at = int(time.time())
        full_content = ""
        tool_uses = []
        
        _debug(f"[Responses] Request: model={model}, log_id={log_id}")
        
        try:
            async with create_async_client(timeout=300, account_proxy_url=account.get_proxy_url()) as client:
                async with client.stream("POST", KIRO_API_URL, json=kiro_request, headers=headers) as response:
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_msg = error_text.decode()[:500]
                        _debug(f"[Responses] Kiro error: {response.status_code} - {error_msg[:200]}")
                        
                        # 打印更多调试信息
                        if response.status_code == 400 and _DEBUG_RESPONSES:
                            cs = kiro_request.get("conversationState", {})
                            hist = cs.get("history", [])
                            _debug(f"[Responses] 400 Debug: history_len={len(hist)}")
                            if hist:
                                # 检查每条 history 的详细结构
                                for i, h in enumerate(hist[:5]):  # 只打印前5条
                                    if "userInputMessage" in h:
                                        uim = h["userInputMessage"]
                                        has_ctx = "userInputMessageContext" in uim
                                        has_tr = has_ctx and "toolResults" in uim.get("userInputMessageContext", {})
                                        content_len = len(uim.get("content", ""))
                                        uim_keys = list(uim.keys())
                                        _debug(f"[Responses]   hist[{i}]: user, keys={uim_keys}, content_len={content_len}, has_toolResults={has_tr}")
                                    elif "assistantResponseMessage" in h:
                                        arm = h["assistantResponseMessage"]
                                        arm_keys = list(arm.keys())
                                        has_tu = "toolUses" in arm
                                        tu_count = len(arm.get("toolUses", []) or []) if has_tu else 0
                                        content_len = len(arm.get("content", "") or "")
                                        _debug(f"[Responses]   hist[{i}]: assistant, keys={arm_keys}, content_len={content_len}, has_toolUses={has_tu}, toolUses_count={tu_count}")
                                    else:
                                        _debug(f"[Responses]   hist[{i}]: UNKNOWN keys={list(h.keys())}")
                                if len(hist) > 5:
                                    _debug(f"[Responses]   ... ({len(hist) - 5} more)")
                            
                            # 打印 currentMessage 结构
                            cm = cs.get("currentMessage", {})
                            if "userInputMessage" in cm:
                                uim = cm["userInputMessage"]
                                _debug(f"[Responses] currentMessage: keys={list(uim.keys())}, content_len={len(uim.get('content', ''))}")
                                if "userInputMessageContext" in uim:
                                    ctx = uim["userInputMessageContext"]
                                    _debug(f"[Responses]   context keys={list(ctx.keys())}")
                                    if "toolResults" in ctx:
                                        _debug(f"[Responses]   toolResults count={len(ctx['toolResults'])}")
                                    if "tools" in ctx:
                                        _debug(f"[Responses]   tools count={len(ctx['tools'])}")
                        
                        # 映射错误代码
                        error_code = "api_error"
                        error_lower = error_msg.lower()
                        if response.status_code == 429 or "rate limit" in error_lower or "throttl" in error_lower:
                            error_code = "rate_limit_exceeded"
                        elif "context" in error_lower or "too long" in error_lower or "content length" in error_lower:
                            error_code = "context_length_exceeded"
                        elif "quota" in error_lower or "insufficient" in error_lower:
                            error_code = "insufficient_quota"
                        elif response.status_code == 401 or response.status_code == 403:
                            error_code = "authentication_error"
                        
                        yield _sse("response.failed", {
                            "type": "response.failed",
                            "response": {
                                "id": response_id,
                                "object": "response",
                                "status": "failed",
                                "error": {"code": error_code, "message": error_msg[:200]}
                            }
                        })
                        return
                    
                    # 1. response.created
                    yield _sse("response.created", {
                        "type": "response.created",
                        "response": {
                            "id": response_id,
                            "object": "response",
                            "created_at": created_at,
                            "status": "in_progress",
                            "model": model,
                            "output": []
                        }
                    })
                    
                    # 2. response.output_item.added
                    yield _sse("response.output_item.added", {
                        "type": "response.output_item.added",
                        "output_index": 0,
                        "item": {
                            "id": item_id,
                            "type": "message",
                            "status": "in_progress",
                            "role": "assistant",
                            "content": []
                        }
                    })
                    
                    # 3. 流式读取并发送 delta
                    full_response = b""
                    async for chunk in response.aiter_bytes():
                        full_response += chunk
                        
                        # 尝试解析增量内容
                        content = _extract_content_from_chunk(chunk)
                        if content:
                            full_content += content
                            yield _sse("response.output_text.delta", {
                                "type": "response.output_text.delta",
                                "item_id": item_id,
                                "output_index": 0,
                                "content_index": 0,
                                "delta": content
                            })
                    
                    # 解析完整响应获取工具调用
                    result = parse_event_stream_full(full_response)
                    tool_uses = result.get("tool_uses", [])
                    if not full_content:
                        full_content = "".join(result.get("content", []))
                    
                    account.request_count += 1
                    account.last_used = time.time()
                    get_rate_limiter().record_request(account.id)
                    
        except Exception as e:
            yield _sse("response.failed", {
                "type": "response.failed",
                "response": {
                    "id": response_id,
                    "status": "failed",
                    "error": {"code": "internal_error", "message": str(e)[:200]}
                }
            })
            return
        
        # 4. response.output_item.done - 消息完成
        message_content = [{"type": "output_text", "text": full_content, "annotations": []}]
        yield _sse("response.output_item.done", {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "id": item_id,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": message_content
            }
        })
        
        # 构建 output 列表
        output_items = [{
            "id": item_id,
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": message_content
        }]
        
        # 5. 工具调用
        for i, tool_use in enumerate(tool_uses):
            tool_item_id = tool_use.get("id", f"call_{uuid.uuid4().hex[:12]}")
            tool_item = {
                "type": "function_call",
                "id": tool_item_id,
                "call_id": tool_item_id,
                "name": tool_use.get("name", ""),
                "arguments": json.dumps(tool_use.get("input", {}))
            }
            
            yield _sse("response.output_item.added", {
                "type": "response.output_item.added",
                "output_index": i + 1,
                "item": tool_item
            })
            
            yield _sse("response.output_item.done", {
                "type": "response.output_item.done",
                "output_index": i + 1,
                "item": tool_item
            })
            
            output_items.append(tool_item)
        
        # 6. response.completed - 必须发送!
        yield _sse("response.completed", {
            "type": "response.completed",
            "response": {
                "id": response_id,
                "object": "response",
                "created_at": created_at,
                "status": "completed",
                "model": model,
                "output": output_items,
                "usage": {
                    "input_tokens": 0,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": 0,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 0
                }
            }
        })
    
    return StreamingResponse(generate(), media_type="text/event-stream")


def _sse(event_type: str, data: dict) -> str:
    """生成 SSE 格式的事件"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _extract_content_from_chunk(chunk: bytes) -> str:
    """从 AWS event-stream chunk 中提取文本内容"""
    content = ""
    pos = 0
    
    while pos < len(chunk):
        if pos + 12 > len(chunk):
            break
        
        total_len = int.from_bytes(chunk[pos:pos+4], 'big')
        if total_len == 0 or total_len > len(chunk) - pos:
            break
        
        headers_len = int.from_bytes(chunk[pos+4:pos+8], 'big')
        payload_start = pos + 12 + headers_len
        payload_end = pos + total_len - 4
        
        if payload_start < payload_end:
            try:
                payload = json.loads(chunk[payload_start:payload_end].decode('utf-8'))
                if 'assistantResponseEvent' in payload:
                    c = payload['assistantResponseEvent'].get('content')
                    if c:
                        content += c
                elif 'content' in payload and 'toolUseId' not in payload:
                    content += payload['content']
            except:
                pass
        
        pos += total_len
    
    return content
