"""OpenAI Responses API 处理 - /v1/responses

Codex CLI 使用的 API 端点，深度适配 Codex 源码
"""
import json
import uuid
import time
import asyncio
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse

from ..config import KIRO_API_URL, map_model_name
from ..core import state, is_retryable_error, stats_manager
from ..core.state import RequestLog
from ..core.history_manager import HistoryManager, get_history_config
from ..core.error_handler import classify_error, ErrorType, format_error_log
from ..core.rate_limiter import get_rate_limiter
from ..kiro_api import build_headers, build_kiro_request, parse_event_stream, parse_event_stream_full, is_quota_exceeded_error


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
    last_was_assistant_with_tools = False
    
    for i, item in enumerate(input_data):
        item_type = item.get("type", "")
        is_last = (i == len(input_data) - 1)
        
        if item_type == "message":
            role = item.get("role", "user")
            content_list = item.get("content", [])
            
            # 提取文本和图片
            text_parts = []
            images = []
            for c in content_list:
                if isinstance(c, str):
                    text_parts.append(c)
                elif isinstance(c, dict):
                    c_type = c.get("type", "")
                    if c_type in ("input_text", "output_text", "text"):
                        text_parts.append(c.get("text", ""))
                    elif c_type == "input_image":
                        image_url = c.get("image_url", "")
                        if image_url.startswith("data:"):
                            import re
                            match = re.match(r'data:image/(\w+);base64,(.+)', image_url)
                            if match:
                                images.append({
                                    "format": match.group(1),
                                    "source": {"bytes": match.group(2)}
                                })
            
            text = "\n".join(text_parts) if text_parts else ""
            
            if role == "user":
                if images:
                    pending_images.extend(images)
                pending_user_texts.append(text)
            
            elif role == "assistant":
                # 遇到 assistant 消息，先处理之前的 user 消息
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
                    # 如果上一个 assistant 有工具调用，这个 user 消息需要带 toolResults
                    if pending_tool_outputs:
                        user_msg["userInputMessage"]["userInputMessageContext"] = {
                            "toolResults": pending_tool_outputs
                        }
                        pending_tool_outputs = []
                    
                    history.append(user_msg)
                    pending_user_texts = []
                elif pending_tool_outputs:
                    # 没有 user 消息，但有工具结果，创建一个带 toolResults 的 user 消息
                    user_msg = {
                        "userInputMessage": {
                            "content": "Tool execution completed.",
                            "modelId": model_id,
                            "origin": "AI_EDITOR",
                            "userInputMessageContext": {
                                "toolResults": pending_tool_outputs
                            }
                        }
                    }
                    history.append(user_msg)
                    pending_tool_outputs = []
                
                # 添加 assistant 消息
                assistant_msg = {
                    "assistantResponseMessage": {
                        "content": text or "I understand."
                    }
                }
                if pending_tool_uses:
                    assistant_msg["assistantResponseMessage"]["toolUses"] = pending_tool_uses
                    pending_tool_uses = []
                    last_was_assistant_with_tools = True
                else:
                    # 没有 toolUses 时不添加这个字段
                    last_was_assistant_with_tools = False
                
                history.append(assistant_msg)
        
        elif item_type == "function_call":
            try:
                args = json.loads(item.get("arguments", "{}")) if isinstance(item.get("arguments"), str) else item.get("arguments", {})
            except:
                args = {}
            
            tool_use = {
                "toolUseId": item.get("call_id", ""),
                "name": item.get("name", ""),
                "input": args
            }
            
            # 如果上一条是 assistant 消息，添加 toolUses
            if history and "assistantResponseMessage" in history[-1]:
                if "toolUses" not in history[-1]["assistantResponseMessage"]:
                    history[-1]["assistantResponseMessage"]["toolUses"] = []
                history[-1]["assistantResponseMessage"]["toolUses"].append(tool_use)
                last_was_assistant_with_tools = True
            else:
                pending_tool_uses.append(tool_use)
        
        elif item_type == "function_call_output":
            call_id = item.get("call_id", "")
            output = item.get("output", {})
            
            # 跳过没有 call_id 的 tool output
            if not call_id:
                print(f"[Responses] Warning: function_call_output without call_id, skipping")
                continue
            
            if isinstance(output, str):
                output_str = output
                status = "success"
            elif isinstance(output, dict):
                output_str = output.get("content", json.dumps(output))
                status = "success" if output.get("success", True) is not False else "error"
            else:
                output_str = str(output)
                status = "success"
            
            pending_tool_outputs.append({
                "content": [{"text": output_str}],
                "status": status,
                "toolUseId": call_id
            })
    
    # 处理剩余的消息
    if pending_user_texts:
        user_content = "\n\n".join(pending_user_texts)
        if not first_user_msg_added and instructions:
            user_content = f"{instructions}\n\n{user_content}"
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
                    print(f"[Responses] Warning: history[{i}] has toolUses but history[{i+1}] has no toolResults, removing toolUses")
                    assistant.pop("toolUses", None)
                elif not has_tool_uses and has_tool_results:
                    # assistant 没有 toolUses 但 user 有 toolResults，清除 toolResults
                    print(f"[Responses] Warning: history[{i}] has no toolUses but history[{i+1}] has toolResults, removing toolResults")
                    user.pop("userInputMessageContext", None)
    
    # 调试日志
    print(f"[Responses] Converted: history={len(history)}, tool_results={len(tool_results)}")
    for i, h in enumerate(history):
        if "userInputMessage" in h:
            has_tr = "toolResults" in h.get("userInputMessage", {}).get("userInputMessageContext", {})
            print(f"[Responses]   history[{i}]: userInputMessage, has_toolResults={has_tr}")
        elif "assistantResponseMessage" in h:
            arm = h.get("assistantResponseMessage", {})
            has_tu_field = "toolUses" in arm
            tu_count = len(arm.get("toolUses", []) or []) if has_tu_field else 0
            print(f"[Responses]   history[{i}]: assistantResponseMessage, has_toolUses_field={has_tu_field}, toolUses_count={tu_count}")
    
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
    kiro_tools = []
    function_count = 0
    
    for tool in tools:
        tool_type = tool.get("type", "")
        
        # 特殊工具类型
        if tool_type == "web_search":
            # Kiro 支持 web_search
            kiro_tools.append({
                "webSearchTool": {
                    "type": "web_search"
                }
            })
            continue
        elif tool_type == "local_shell":
            # local_shell 是 OpenAI 原生工具，Kiro 不支持，跳过
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
                description = func.get("description", "")[:500]
                parameters = func.get("parameters", {"type": "object", "properties": {}})
            else:
                # Responses API 格式
                name = tool.get("name", "")
                description = tool.get("description", "")[:500]
                parameters = tool.get("parameters", {"type": "object", "properties": {}})
        elif tool_type == "custom":
            # 自定义工具格式
            name = tool.get("name", "")
            description = tool.get("description", "")[:500]
            # custom 工具可能有不同的 schema 格式
            fmt = tool.get("format", {})
            if fmt.get("type") == "json_schema":
                parameters = fmt.get("schema", {"type": "object", "properties": {}})
            else:
                parameters = {"type": "object", "properties": {}}
        else:
            name = tool.get("name", "")
            description = tool.get("description", "")[:500]
            parameters = tool.get("parameters", tool.get("input_schema", {"type": "object", "properties": {}}))
        
        if not name:
            continue
        
        function_count += 1
        
        # 转换为 Kiro 格式
        kiro_tools.append({
            "toolSpecification": {
                "name": name,
                "description": description or f"Tool: {name}",
                "inputSchema": {
                    "json": parameters
                }
            }
        })
    
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
    
    creds = account.get_credentials()
    headers = build_headers(
        token,
        machine_id=account.get_machine_id(),
        profile_arn=creds.profile_arn if creds else None,
        client_id=creds.client_id if creds else None
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
    
    # 对于 Responses API，强制启用自动截断（Codex CLI 的历史可能很长）
    from ..core.history_manager import TruncateStrategy
    if TruncateStrategy.AUTO_TRUNCATE not in history_manager.config.strategies:
        history_manager.config.strategies.append(TruncateStrategy.AUTO_TRUNCATE)
    
    # 创建摘要 API 调用函数
    async def api_caller(prompt: str) -> str:
        req = build_kiro_request(prompt, "claude-haiku-4.5", [])
        try:
            async with httpx.AsyncClient(verify=False, timeout=60) as client:
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
    if isinstance(input_data, list):
        for i, item in enumerate(input_data):
            item_type = item.get("type", "?")
            role = item.get("role", "?")
            print(f"[Responses] input[{i}]: type={item_type}, role={role}")
        print(f"[Responses] history len: {len(history)}, tool_results len: {len(tool_results)}, images: {len(images) if images else 0}")
        print(f"[Responses] user_content len: {len(user_content)}")
    
    # 验证 tool_results 与 history 的一致性
    if tool_results and history:
        # 找到最后一个 assistant 消息
        last_assistant = None
        last_assistant_idx = -1
        for i, msg in enumerate(reversed(history)):
            if "assistantResponseMessage" in msg:
                last_assistant = msg["assistantResponseMessage"]
                last_assistant_idx = len(history) - 1 - i
                break
        
        if last_assistant:
            tool_use_ids = set()
            for tu in last_assistant.get("toolUses", []) or []:
                tu_id = tu.get("toolUseId")
                if tu_id:
                    tool_use_ids.add(tu_id)
            
            print(f"[Responses] Last assistant at idx={last_assistant_idx}, toolUse_ids={tool_use_ids}")
            print(f"[Responses] tool_results ids={[tr.get('toolUseId') for tr in tool_results]}")
            
            # 过滤 tool_results，只保留有对应 toolUse 的
            if tool_use_ids:
                filtered_results = [tr for tr in tool_results if tr.get("toolUseId") in tool_use_ids]
                if len(filtered_results) != len(tool_results):
                    print(f"[Responses] Filtered tool_results: {len(tool_results)} -> {len(filtered_results)}")
                    tool_results = filtered_results
            else:
                # 如果最后一个 assistant 没有 toolUses，清空 tool_results
                print(f"[Responses] Warning: Last assistant has no toolUses, clearing tool_results")
                tool_results = []
        else:
            print(f"[Responses] Warning: No assistant message in history, clearing tool_results")
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
        tool_results=tool_results if tool_results else None
    )
    
    # 调试：打印完整的 Kiro 请求（使用深拷贝避免修改原始请求）
    if tool_results:
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
        print(f"[Responses] Kiro request structure: {json.dumps(debug_request, indent=2)}")
    
    if stream:
        return await _handle_stream(kiro_request, headers, account, model, log_id, start_time)
    
    # 非流式
    status_code = 0
    error_msg = None
    try:
        async with httpx.AsyncClient(verify=False, timeout=120) as client:
            resp = await client.post(KIRO_API_URL, json=kiro_request, headers=headers)
            status_code = resp.status_code
            if resp.status_code != 200:
                error_msg = resp.text[:500]
                raise HTTPException(resp.status_code, resp.text)

            result = parse_event_stream_full(resp.content)
            account.request_count += 1
            account.last_used = time.time()
            get_rate_limiter().record_request(account.id)

            return _build_response(result, model, log_id)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        status_code = 500
        raise
    finally:
        duration = (time.time() - start_time) * 1000
        state.add_log(RequestLog(
            id=log_id,
            timestamp=time.time(),
            method="POST",
            path="/v1/responses",
            model=model,
            account_id=account.id if account else None,
            status=status_code,
            duration_ms=duration,
            error=error_msg
        ))
        stats_manager.record_request(
            account_id=account.id if account else "unknown",
            model=model,
            success=status_code == 200,
            duration_ms=duration
        )


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
        output.append({
            "type": "function_call",
            "id": tool_use.get("id", f"call_{uuid.uuid4().hex[:12]}"),
            "call_id": tool_use.get("id", f"call_{uuid.uuid4().hex[:12]}"),
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
    
    # 保存完整请求用于调试
    import os
    debug_dir = "debug_requests"
    os.makedirs(debug_dir, exist_ok=True)
    debug_file = f"{debug_dir}/{log_id}_request.json"
    with open(debug_file, 'w', encoding='utf-8') as f:
        json.dump(kiro_request, f, indent=2, ensure_ascii=False)
    print(f"[Responses] Saved request to {debug_file}")
    
    async def generate():
        response_id = f"resp_{log_id}"
        item_id = f"msg_{log_id}"
        created_at = int(time.time())
        full_content = ""
        tool_uses = []
        error_occurred = False
        
        print(f"[Responses] Request: model={model}, log_id={log_id}")
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=300) as client:
                async with client.stream("POST", KIRO_API_URL, json=kiro_request, headers=headers) as response:
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_msg = error_text.decode()[:500]
                        print(f"[Responses] Kiro error: {response.status_code} - {error_msg[:200]}")
                        
                        # 打印更多调试信息
                        if response.status_code == 400:
                            cs = kiro_request.get("conversationState", {})
                            hist = cs.get("history", [])
                            print(f"[Responses] 400 Debug: history_len={len(hist)}")
                            if hist:
                                # 检查每条 history 的详细结构
                                for i, h in enumerate(hist[:5]):  # 只打印前5条
                                    if "userInputMessage" in h:
                                        uim = h["userInputMessage"]
                                        has_ctx = "userInputMessageContext" in uim
                                        has_tr = has_ctx and "toolResults" in uim.get("userInputMessageContext", {})
                                        content_len = len(uim.get("content", ""))
                                        uim_keys = list(uim.keys())
                                        print(f"[Responses]   hist[{i}]: user, keys={uim_keys}, content_len={content_len}, has_toolResults={has_tr}")
                                    elif "assistantResponseMessage" in h:
                                        arm = h["assistantResponseMessage"]
                                        arm_keys = list(arm.keys())
                                        has_tu = "toolUses" in arm
                                        tu_count = len(arm.get("toolUses", []) or []) if has_tu else 0
                                        content_len = len(arm.get("content", "") or "")
                                        print(f"[Responses]   hist[{i}]: assistant, keys={arm_keys}, content_len={content_len}, has_toolUses={has_tu}, toolUses_count={tu_count}")
                                    else:
                                        print(f"[Responses]   hist[{i}]: UNKNOWN keys={list(h.keys())}")
                                if len(hist) > 5:
                                    print(f"[Responses]   ... ({len(hist) - 5} more)")
                            
                            # 打印 currentMessage 结构
                            cm = cs.get("currentMessage", {})
                            if "userInputMessage" in cm:
                                uim = cm["userInputMessage"]
                                print(f"[Responses] currentMessage: keys={list(uim.keys())}, content_len={len(uim.get('content', ''))}")
                                if "userInputMessageContext" in uim:
                                    ctx = uim["userInputMessageContext"]
                                    print(f"[Responses]   context keys={list(ctx.keys())}")
                                    if "toolResults" in ctx:
                                        print(f"[Responses]   toolResults count={len(ctx['toolResults'])}")
                                    if "tools" in ctx:
                                        print(f"[Responses]   tools count={len(ctx['tools'])}")
                        
                        error_occurred = True
                        
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
                        duration = (time.time() - start_time) * 1000
                        state.add_log(RequestLog(
                            id=log_id,
                            timestamp=time.time(),
                            method="POST",
                            path="/v1/responses (stream)",
                            model=model,
                            account_id=account.id if account else None,
                            status=response.status_code,
                            duration_ms=duration,
                            error=error_msg[:200]
                        ))
                        stats_manager.record_request(
                            account_id=account.id if account else "unknown",
                            model=model,
                            success=False,
                            duration_ms=duration
                        )
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
            error_occurred = True
            yield _sse("response.failed", {
                "type": "response.failed",
                "response": {
                    "id": response_id,
                    "status": "failed",
                    "error": {"code": "internal_error", "message": str(e)[:200]}
                }
            })
            duration = (time.time() - start_time) * 1000
            state.add_log(RequestLog(
                id=log_id,
                timestamp=time.time(),
                method="POST",
                path="/v1/responses (stream)",
                model=model,
                account_id=account.id if account else None,
                status=500,
                duration_ms=duration,
                error=str(e)[:200]
            ))
            stats_manager.record_request(
                account_id=account.id if account else "unknown",
                model=model,
                success=False,
                duration_ms=duration
            )
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

        # 记录成功的流式请求日志
        duration = (time.time() - start_time) * 1000
        state.add_log(RequestLog(
            id=log_id,
            timestamp=time.time(),
            method="POST",
            path="/v1/responses (stream)",
            model=model,
            account_id=account.id if account else None,
            status=200,
            duration_ms=duration,
            error=None
        ))
        stats_manager.record_request(
            account_id=account.id if account else "unknown",
            model=model,
            success=True,
            duration_ms=duration
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


def _sse(event_type: str, data: dict) -> str:
    """生成 SSE 格式的事件"""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


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
