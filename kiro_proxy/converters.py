"""协议转换模块 - Anthropic/OpenAI/Gemini <-> Kiro

增强版：参考 proxycast 实现
- 工具数量限制（最多 50 个）
- 工具描述截断（最多 500 字符）
- 历史消息交替修复
- OpenAI tool 角色消息处理
- tool_choice: required 支持
- web_search 特殊工具支持
- tool_results 去重
"""
import json
import hashlib
import re
from typing import List, Dict, Any, Tuple, Optional

# 常量
MAX_TOOLS = 50
MAX_TOOL_DESCRIPTION_LENGTH = 500


def generate_session_id(messages: list) -> str:
    """基于消息内容生成会话ID"""
    content = json.dumps(messages[:3], sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def extract_images_from_content(content) -> Tuple[str, List[dict]]:
    """从消息内容中提取文本和图片
    
    Returns:
        (text_content, images_list)
    """
    if isinstance(content, str):
        return content, []
    
    if not isinstance(content, list):
        return str(content) if content else "", []
    
    text_parts = []
    images = []
    
    for block in content:
        if isinstance(block, str):
            text_parts.append(block)
        elif isinstance(block, dict):
            block_type = block.get("type", "")
            
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            
            elif block_type == "image":
                # Anthropic 格式
                source = block.get("source", {})
                media_type = source.get("media_type", "image/jpeg")
                data = source.get("data", "")
                
                fmt = "jpeg"
                if "png" in media_type:
                    fmt = "png"
                elif "gif" in media_type:
                    fmt = "gif"
                elif "webp" in media_type:
                    fmt = "webp"
                
                if data:
                    images.append({
                        "format": fmt,
                        "source": {"bytes": data}
                    })
            
            elif block_type == "image_url":
                # OpenAI 格式
                image_url = block.get("image_url", {})
                url = image_url.get("url", "")
                
                if url.startswith("data:"):
                    match = re.match(r'data:image/(\w+);base64,(.+)', url)
                    if match:
                        fmt = match.group(1)
                        data = match.group(2)
                        images.append({
                            "format": fmt,
                            "source": {"bytes": data}
                        })
    
    return "\n".join(text_parts), images


def truncate_description(desc: str, max_length: int = MAX_TOOL_DESCRIPTION_LENGTH) -> str:
    """截断工具描述"""
    if len(desc) <= max_length:
        return desc
    return desc[:max_length - 3] + "..."


# ==================== Anthropic 转换 ====================

def convert_anthropic_tools_to_kiro(tools: List[dict]) -> List[dict]:
    """将 Anthropic 工具格式转换为 Kiro 格式
    
    增强：
    - 限制最多 50 个工具
    - 截断过长的描述
    - 支持 web_search 特殊工具
    """
    kiro_tools = []
    function_count = 0
    
    for tool in tools:
        name = tool.get("name", "")
        
        # 特殊工具：web_search
        if name in ("web_search", "web_search_20250305"):
            kiro_tools.append({
                "webSearchTool": {
                    "type": "web_search"
                }
            })
            continue
        
        # 限制工具数量
        if function_count >= MAX_TOOLS:
            continue
        function_count += 1
        
        description = tool.get("description", f"Tool: {name}")
        description = truncate_description(description)
        
        input_schema = tool.get("input_schema", {"type": "object", "properties": {}})
        
        kiro_tools.append({
            "toolSpecification": {
                "name": name,
                "description": description,
                "inputSchema": {
                    "json": input_schema
                }
            }
        })
    
    return kiro_tools


def fix_history_alternation(history: List[dict], model_id: str = "claude-sonnet-4") -> List[dict]:
    """修复历史记录，确保 user/assistant 严格交替
    
    Kiro API 要求消息必须严格交替：user -> assistant -> user -> assistant
    """
    if not history:
        return history
    
    fixed = []
    
    for item in history:
        is_user = "userInputMessage" in item
        is_assistant = "assistantResponseMessage" in item
        
        if is_user:
            # 检查上一条是否也是 user
            if fixed and "userInputMessage" in fixed[-1]:
                # 检查当前消息是否有 tool_results
                has_tool_results = (
                    item.get("userInputMessage", {})
                    .get("userInputMessageContext", {})
                    .get("toolResults")
                )
                
                if has_tool_results:
                    # 合并 tool_results 到上一条 user 消息
                    new_results = has_tool_results
                    last_user = fixed[-1]["userInputMessage"]
                    
                    if "userInputMessageContext" not in last_user:
                        last_user["userInputMessageContext"] = {}
                    
                    ctx = last_user["userInputMessageContext"]
                    if "toolResults" in ctx and ctx["toolResults"]:
                        ctx["toolResults"].extend(new_results)
                    else:
                        ctx["toolResults"] = new_results
                    continue
                else:
                    # 插入一个占位 assistant 消息
                    fixed.append({
                        "assistantResponseMessage": {
                            "content": "I understand.",
                            "toolUses": []
                        }
                    })
            
            fixed.append(item)
        
        elif is_assistant:
            # 检查上一条是否也是 assistant
            if fixed and "assistantResponseMessage" in fixed[-1]:
                # 插入一个占位 user 消息
                fixed.append({
                    "userInputMessage": {
                        "content": "Continue",
                        "modelId": model_id,
                        "origin": "AI_EDITOR"
                    }
                })
            
            # 如果历史为空，先插入一个 user 消息
            if not fixed:
                fixed.append({
                    "userInputMessage": {
                        "content": "Continue",
                        "modelId": model_id,
                        "origin": "AI_EDITOR"
                    }
                })
            
            fixed.append(item)
    
    # 确保以 assistant 结尾（如果最后是 user，添加占位 assistant）
    if fixed and "userInputMessage" in fixed[-1]:
        fixed.append({
            "assistantResponseMessage": {
                "content": "I understand.",
                "toolUses": []
            }
        })
    
    return fixed


def convert_anthropic_messages_to_kiro(messages: List[dict], system="") -> Tuple[str, List[dict], List[dict]]:
    """将 Anthropic 消息格式转换为 Kiro 格式
    
    Returns:
        (user_content, history, tool_results)
    """
    history = []
    user_content = ""
    current_tool_results = []
    
    # 处理 system
    system_text = ""
    if isinstance(system, list):
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                system_text += block.get("text", "") + "\n"
            elif isinstance(block, str):
                system_text += block + "\n"
        system_text = system_text.strip()
    elif isinstance(system, str):
        system_text = system
    
    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")
        is_last = (i == len(messages) - 1)
        
        # 处理 content 列表
        tool_results = []
        text_parts = []
        
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        tr_content = block.get("content", "")
                        if isinstance(tr_content, list):
                            tr_text_parts = []
                            for tc in tr_content:
                                if isinstance(tc, dict) and tc.get("type") == "text":
                                    tr_text_parts.append(tc.get("text", ""))
                                elif isinstance(tc, str):
                                    tr_text_parts.append(tc)
                            tr_content = "\n".join(tr_text_parts)
                        
                        # 处理 is_error
                        status = "error" if block.get("is_error") else "success"
                        
                        tool_results.append({
                            "content": [{"text": str(tr_content)}],
                            "status": status,
                            "toolUseId": block.get("tool_use_id", "")
                        })
                elif isinstance(block, str):
                    text_parts.append(block)
            
            content = "\n".join(text_parts) if text_parts else ""
        
        # 处理工具结果
        if tool_results:
            # 去重
            seen_ids = set()
            unique_results = []
            for tr in tool_results:
                if tr["toolUseId"] not in seen_ids:
                    seen_ids.add(tr["toolUseId"])
                    unique_results.append(tr)
            tool_results = unique_results
            
            if is_last:
                current_tool_results = tool_results
                user_content = content if content else "Tool results provided."
            else:
                history.append({
                    "userInputMessage": {
                        "content": content if content else "Tool results provided.",
                        "modelId": "claude-sonnet-4",
                        "origin": "AI_EDITOR",
                        "userInputMessageContext": {
                            "toolResults": tool_results
                        }
                    }
                })
            continue
        
        if role == "user":
            if system_text and not history:
                content = f"{system_text}\n\n{content}" if content else system_text
            
            if is_last:
                user_content = content if content else "Continue"
            else:
                history.append({
                    "userInputMessage": {
                        "content": content if content else "Continue",
                        "modelId": "claude-sonnet-4",
                        "origin": "AI_EDITOR"
                    }
                })
        
        elif role == "assistant":
            tool_uses = []
            assistant_text = ""
            
            if isinstance(msg.get("content"), list):
                text_parts = []
                for block in msg["content"]:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            tool_uses.append({
                                "toolUseId": block.get("id", ""),
                                "name": block.get("name", ""),
                                "input": block.get("input", {})
                            })
                        elif block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                assistant_text = "\n".join(text_parts)
            else:
                assistant_text = content if isinstance(content, str) else ""
            
            # 确保 assistant 消息有内容
            if not assistant_text:
                assistant_text = "I understand."
            
            history.append({
                "assistantResponseMessage": {
                    "content": assistant_text,
                    "toolUses": tool_uses
                }
            })
    
    # 修复历史交替
    history = fix_history_alternation(history)
    
    return user_content, history, current_tool_results


def convert_kiro_response_to_anthropic(result: dict, model: str, msg_id: str) -> dict:
    """将 Kiro 响应转换为 Anthropic 格式"""
    content = []
    text = "".join(result["content"])
    if text:
        content.append({"type": "text", "text": text})
    
    for tool_use in result["tool_uses"]:
        content.append(tool_use)
    
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": model,
        "stop_reason": result["stop_reason"],
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 100}
    }


# ==================== OpenAI 转换 ====================

def is_tool_choice_required(tool_choice) -> bool:
    """检查 tool_choice 是否为 required"""
    if isinstance(tool_choice, dict):
        t = tool_choice.get("type", "")
        return t in ("any", "tool", "required")
    elif isinstance(tool_choice, str):
        return tool_choice in ("required", "any")
    return False


def convert_openai_tools_to_kiro(tools: List[dict]) -> List[dict]:
    """将 OpenAI 工具格式转换为 Kiro 格式"""
    kiro_tools = []
    function_count = 0
    
    for tool in tools:
        tool_type = tool.get("type", "function")
        
        # 特殊工具
        if tool_type == "web_search":
            kiro_tools.append({
                "webSearchTool": {
                    "type": "web_search"
                }
            })
            continue
        
        if tool_type != "function":
            continue
        
        # 限制工具数量
        if function_count >= MAX_TOOLS:
            continue
        function_count += 1
        
        func = tool.get("function", {})
        name = func.get("name", "")
        description = func.get("description", f"Tool: {name}")
        description = truncate_description(description)
        parameters = func.get("parameters", {"type": "object", "properties": {}})
        
        kiro_tools.append({
            "toolSpecification": {
                "name": name,
                "description": description,
                "inputSchema": {
                    "json": parameters
                }
            }
        })
    
    return kiro_tools


def convert_openai_messages_to_kiro(
    messages: List[dict], 
    model: str,
    tools: List[dict] = None,
    tool_choice = None
) -> Tuple[str, List[dict], List[dict], List[dict]]:
    """将 OpenAI 消息格式转换为 Kiro 格式
    
    增强：
    - 支持 tool 角色消息
    - 支持 assistant 的 tool_calls
    - 支持 tool_choice: required
    - 历史交替修复
    
    Returns:
        (user_content, history, tool_results, kiro_tools)
    """
    system_content = ""
    history = []
    user_content = ""
    current_tool_results = []
    pending_tool_results = []  # 待处理的 tool 消息
    
    # 处理 tool_choice: required
    tool_instruction = ""
    if is_tool_choice_required(tool_choice) and tools:
        tool_instruction = "\n\n[CRITICAL INSTRUCTION] You MUST use one of the provided tools to respond. Do NOT respond with plain text. Call a tool function immediately."
    
    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")
        is_last = (i == len(messages) - 1)
        
        # 提取文本内容
        if isinstance(content, list):
            content = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
        if not content:
            content = ""
        
        if role == "system":
            system_content = content + tool_instruction
        
        elif role == "tool":
            # OpenAI tool 角色消息 -> Kiro toolResults
            tool_call_id = msg.get("tool_call_id", "")
            pending_tool_results.append({
                "content": [{"text": str(content)}],
                "status": "success",
                "toolUseId": tool_call_id
            })
        
        elif role == "user":
            # 如果有待处理的 tool results，先处理
            if pending_tool_results:
                # 去重
                seen_ids = set()
                unique_results = []
                for tr in pending_tool_results:
                    if tr["toolUseId"] not in seen_ids:
                        seen_ids.add(tr["toolUseId"])
                        unique_results.append(tr)
                
                if is_last:
                    current_tool_results = unique_results
                else:
                    history.append({
                        "userInputMessage": {
                            "content": "Tool results provided.",
                            "modelId": model,
                            "origin": "AI_EDITOR",
                            "userInputMessageContext": {
                                "toolResults": unique_results
                            }
                        }
                    })
                pending_tool_results = []
            
            # 合并 system prompt
            if system_content and not history:
                content = f"{system_content}\n\n{content}"
            
            if is_last:
                user_content = content
            else:
                history.append({
                    "userInputMessage": {
                        "content": content,
                        "modelId": model,
                        "origin": "AI_EDITOR"
                    }
                })
        
        elif role == "assistant":
            # 如果有待处理的 tool results，先创建 user 消息
            if pending_tool_results:
                seen_ids = set()
                unique_results = []
                for tr in pending_tool_results:
                    if tr["toolUseId"] not in seen_ids:
                        seen_ids.add(tr["toolUseId"])
                        unique_results.append(tr)
                
                history.append({
                    "userInputMessage": {
                        "content": "Tool results provided.",
                        "modelId": model,
                        "origin": "AI_EDITOR",
                        "userInputMessageContext": {
                            "toolResults": unique_results
                        }
                    }
                })
                pending_tool_results = []
            
            # 处理 tool_calls
            tool_uses = []
            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except:
                    args = {}
                
                tool_uses.append({
                    "toolUseId": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "input": args
                })
            
            assistant_text = content if content else "I understand."
            
            history.append({
                "assistantResponseMessage": {
                    "content": assistant_text,
                    "toolUses": tool_uses
                }
            })
    
    # 处理末尾的 tool results
    if pending_tool_results:
        seen_ids = set()
        unique_results = []
        for tr in pending_tool_results:
            if tr["toolUseId"] not in seen_ids:
                seen_ids.add(tr["toolUseId"])
                unique_results.append(tr)
        current_tool_results = unique_results
        if not user_content:
            user_content = "Tool results provided."
    
    # 如果没有用户消息
    if not user_content:
        user_content = messages[-1].get("content", "") if messages else "Continue"
        if isinstance(user_content, list):
            user_content = " ".join([c.get("text", "") for c in user_content if c.get("type") == "text"])
        if not user_content:
            user_content = "Continue"
    
    # 历史不包含最后一条用户消息
    if history and "userInputMessage" in history[-1]:
        history = history[:-1]
    
    # 修复历史交替
    history = fix_history_alternation(history, model)
    
    # 转换工具
    kiro_tools = convert_openai_tools_to_kiro(tools) if tools else []
    
    return user_content, history, current_tool_results, kiro_tools


def convert_kiro_response_to_openai(result: dict, model: str, msg_id: str) -> dict:
    """将 Kiro 响应转换为 OpenAI 格式"""
    text = "".join(result["content"])
    tool_calls = []
    
    for tool_use in result.get("tool_uses", []):
        if tool_use.get("type") == "tool_use":
            tool_calls.append({
                "id": tool_use.get("id", ""),
                "type": "function",
                "function": {
                    "name": tool_use.get("name", ""),
                    "arguments": json.dumps(tool_use.get("input", {}))
                }
            })
    
    # 映射 stop_reason
    stop_reason = result.get("stop_reason", "stop")
    finish_reason = "tool_calls" if tool_calls else "stop"
    if stop_reason == "max_tokens":
        finish_reason = "length"
    
    message = {
        "role": "assistant",
        "content": text if text else None
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
    
    return {
        "id": msg_id,
        "object": "chat.completion",
        "model": model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 100,
            "total_tokens": 200
        }
    }


# ==================== Gemini 转换 ====================

def convert_gemini_tools_to_kiro(tools: List[dict]) -> List[dict]:
    """将 Gemini 工具格式转换为 Kiro 格式
    
    Gemini 工具格式：
    {
        "functionDeclarations": [
            {
                "name": "get_weather",
                "description": "Get weather info",
                "parameters": {...}
            }
        ]
    }
    """
    kiro_tools = []
    function_count = 0
    
    for tool in tools:
        # Gemini 的工具定义在 functionDeclarations 中
        declarations = tool.get("functionDeclarations", [])
        
        for func in declarations:
            # 限制工具数量
            if function_count >= MAX_TOOLS:
                break
            function_count += 1
            
            name = func.get("name", "")
            description = func.get("description", f"Tool: {name}")
            description = truncate_description(description)
            parameters = func.get("parameters", {"type": "object", "properties": {}})
            
            kiro_tools.append({
                "toolSpecification": {
                    "name": name,
                    "description": description,
                    "inputSchema": {
                        "json": parameters
                    }
                }
            })
    
    return kiro_tools


def convert_gemini_contents_to_kiro(
    contents: List[dict], 
    system_instruction: dict, 
    model: str,
    tools: List[dict] = None,
    tool_config: dict = None
) -> Tuple[str, List[dict], List[dict], List[dict]]:
    """将 Gemini 消息格式转换为 Kiro 格式
    
    增强：
    - 支持 functionCall 和 functionResponse
    - 支持 tool_config
    
    Returns:
        (user_content, history, tool_results, kiro_tools)
    """
    history = []
    user_content = ""
    current_tool_results = []
    pending_tool_results = []
    
    # 处理 system instruction
    system_text = ""
    if system_instruction:
        parts = system_instruction.get("parts", [])
        system_text = " ".join(p.get("text", "") for p in parts if "text" in p)
    
    # 处理 tool_config（类似 tool_choice）
    tool_instruction = ""
    if tool_config:
        mode = tool_config.get("functionCallingConfig", {}).get("mode", "")
        if mode in ("ANY", "REQUIRED"):
            tool_instruction = "\n\n[CRITICAL INSTRUCTION] You MUST use one of the provided tools to respond. Do NOT respond with plain text."
    
    for i, content in enumerate(contents):
        role = content.get("role", "user")
        parts = content.get("parts", [])
        is_last = (i == len(contents) - 1)
        
        # 提取文本和工具调用
        text_parts = []
        tool_calls = []
        tool_responses = []
        
        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                # Gemini 的工具调用
                fc = part["functionCall"]
                tool_calls.append({
                    "toolUseId": fc.get("name", "") + "_" + str(i),  # Gemini 没有 ID，生成一个
                    "name": fc.get("name", ""),
                    "input": fc.get("args", {})
                })
            elif "functionResponse" in part:
                # Gemini 的工具响应
                fr = part["functionResponse"]
                response_content = fr.get("response", {})
                if isinstance(response_content, dict):
                    response_text = json.dumps(response_content)
                else:
                    response_text = str(response_content)
                
                tool_responses.append({
                    "content": [{"text": response_text}],
                    "status": "success",
                    "toolUseId": fr.get("name", "") + "_" + str(i - 1)  # 匹配上一个调用
                })
        
        text = " ".join(text_parts)
        
        if role == "user":
            # 处理待处理的 tool responses
            if pending_tool_results:
                seen_ids = set()
                unique_results = []
                for tr in pending_tool_results:
                    if tr["toolUseId"] not in seen_ids:
                        seen_ids.add(tr["toolUseId"])
                        unique_results.append(tr)
                
                history.append({
                    "userInputMessage": {
                        "content": "Tool results provided.",
                        "modelId": model,
                        "origin": "AI_EDITOR",
                        "userInputMessageContext": {
                            "toolResults": unique_results
                        }
                    }
                })
                pending_tool_results = []
            
            # 处理 functionResponse（用户消息中的工具响应）
            if tool_responses:
                pending_tool_results.extend(tool_responses)
            
            # 合并 system prompt
            if system_text and not history:
                text = f"{system_text}{tool_instruction}\n\n{text}"
            
            if is_last:
                user_content = text
                if pending_tool_results:
                    current_tool_results = pending_tool_results
                    pending_tool_results = []
            else:
                if text:
                    history.append({
                        "userInputMessage": {
                            "content": text,
                            "modelId": model,
                            "origin": "AI_EDITOR"
                        }
                    })
        
        elif role == "model":
            # 处理待处理的 tool responses
            if pending_tool_results:
                seen_ids = set()
                unique_results = []
                for tr in pending_tool_results:
                    if tr["toolUseId"] not in seen_ids:
                        seen_ids.add(tr["toolUseId"])
                        unique_results.append(tr)
                
                history.append({
                    "userInputMessage": {
                        "content": "Tool results provided.",
                        "modelId": model,
                        "origin": "AI_EDITOR",
                        "userInputMessageContext": {
                            "toolResults": unique_results
                        }
                    }
                })
                pending_tool_results = []
            
            assistant_text = text if text else "I understand."
            
            history.append({
                "assistantResponseMessage": {
                    "content": assistant_text,
                    "toolUses": tool_calls
                }
            })
    
    # 处理末尾的 tool results
    if pending_tool_results:
        current_tool_results = pending_tool_results
        if not user_content:
            user_content = "Tool results provided."
    
    # 如果没有用户消息
    if not user_content:
        if contents:
            last_parts = contents[-1].get("parts", [])
            user_content = " ".join(p.get("text", "") for p in last_parts if "text" in p)
        if not user_content:
            user_content = "Continue"
    
    # 修复历史交替
    history = fix_history_alternation(history, model)
    
    # 移除最后一条（当前用户消息）
    if history and "userInputMessage" in history[-1]:
        history = history[:-1]
    
    # 转换工具
    kiro_tools = convert_gemini_tools_to_kiro(tools) if tools else []
    
    return user_content, history, current_tool_results, kiro_tools


def convert_kiro_response_to_gemini(result: dict, model: str) -> dict:
    """将 Kiro 响应转换为 Gemini 格式"""
    text = "".join(result.get("content", []))
    tool_uses = result.get("tool_uses", [])
    
    parts = []
    
    # 添加文本部分
    if text:
        parts.append({"text": text})
    
    # 添加工具调用
    for tool_use in tool_uses:
        if tool_use.get("type") == "tool_use":
            parts.append({
                "functionCall": {
                    "name": tool_use.get("name", ""),
                    "args": tool_use.get("input", {})
                }
            })
    
    # 映射 stop_reason
    stop_reason = result.get("stop_reason", "STOP")
    finish_reason = "STOP"
    if tool_uses:
        finish_reason = "TOOL_CALLS"
    elif stop_reason == "max_tokens":
        finish_reason = "MAX_TOKENS"
    
    return {
        "candidates": [{
            "content": {
                "parts": parts,
                "role": "model"
            },
            "finishReason": finish_reason,
            "index": 0
        }],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 100,
            "totalTokenCount": 200
        }
    }
