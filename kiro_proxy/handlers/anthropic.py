"""Anthropic 协议处理 - /v1/messages"""
import json
import uuid
import time
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse

from ..config import KIRO_API_URL, map_model_name
from ..models import state, RequestLog
from ..kiro_api import build_headers, build_kiro_request, parse_event_stream_full
from ..converters import (
    generate_session_id,
    convert_anthropic_tools_to_kiro,
    convert_anthropic_messages_to_kiro,
    convert_kiro_response_to_anthropic,
    extract_images_from_content
)


def _extract_text_from_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            parts.append(_extract_text_from_content(item))
        return "".join(parts)
    if isinstance(content, dict):
        if "text" in content and isinstance(content.get("text"), str):
            return content["text"]
        if "content" in content:
            return _extract_text_from_content(content.get("content"))
    return ""


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + 3) // 4


def _count_tokens_from_messages(messages, system: str = "") -> int:
    total = _estimate_tokens(system) if system else 0
    for msg in messages or []:
        total += _estimate_tokens(_extract_text_from_content(msg.get("content")))
    return total


def _classify_kiro_error(error_text: str):
    lowered = error_text.lower()
    if "model_temporarily_unavailable" in error_text or "unexpectedly high load" in lowered:
        return 503, "overloaded_error", "Model temporarily unavailable, please retry."
    if "content_length_exceeds_threshold" in error_text or "too long" in lowered:
        return 400, "invalid_request_error", "Conversation too long, please /clear or start a new chat."
    return 500, "api_error", "Upstream API error."


async def handle_count_tokens(request: Request):
    '''Handle /v1/messages/count_tokens requests.'''
    body = await request.json()
    messages = body.get("messages", [])
    system = body.get("system", "")
    if not messages and not system:
        raise HTTPException(400, "messages required")
    return {"input_tokens": _count_tokens_from_messages(messages, system)}


async def handle_messages(request: Request):
    """处理 /v1/messages 请求"""
    start_time = time.time()
    log_id = uuid.uuid4().hex[:8]
    
    body = await request.json()
    model = map_model_name(body.get("model", "claude-sonnet-4"))
    messages = body.get("messages", [])
    system = body.get("system", "")
    stream = body.get("stream", False)
    tools = body.get("tools", [])
    
    if not messages:
        raise HTTPException(400, "messages required")
    
    session_id = generate_session_id(messages)
    account = state.get_available_account(session_id)
    
    if not account:
        raise HTTPException(503, "All accounts are rate limited")
    
    token = account.get_token()
    if not token:
        raise HTTPException(500, f"Failed to get token for account {account.name}")
    
    # 转换消息格式
    user_content, history, tool_results = convert_anthropic_messages_to_kiro(messages, system)
    
    # 提取最后一条消息中的图片
    images = []
    if messages:
        last_msg = messages[-1]
        if last_msg.get("role") == "user":
            _, images = extract_images_from_content(last_msg.get("content", ""))
    
    # 构建 Kiro 请求
    kiro_tools = convert_anthropic_tools_to_kiro(tools) if tools else None
    kiro_request = build_kiro_request(user_content, model, history, kiro_tools, images, tool_results)
    
    headers = build_headers(token)
    error_msg = None
    status_code = 200
    
    if stream:
        return await _handle_stream(kiro_request, headers, account, model, log_id, start_time)
    else:
        return await _handle_non_stream(kiro_request, headers, account, model, log_id, start_time)


async def _handle_stream(kiro_request, headers, account, model, log_id, start_time):
    """Handle streaming responses."""
    async def generate():
        try:
            async with httpx.AsyncClient(verify=False, timeout=300) as client:
                async with client.stream("POST", KIRO_API_URL, json=kiro_request, headers=headers) as response:
                    if response.status_code == 429:
                        state.mark_rate_limited(account.id)
                        yield f'data: {{"type":"error","error":{{"type":"rate_limit_error","message":"Rate limited"}}}}\n\n'
                        return

                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_str = error_text.decode()
                        print(f"=== Kiro API Error ===")
                        print(f"Status: {response.status_code}")
                        print(f"Response: {error_str[:500]}")
                        print(f"======================")

                        _, error_type, error_msg = _classify_kiro_error(error_str)
                        yield f'data: {{"type":"error","error":{{"type":"{error_type}","message":"{error_msg}"}}}}\n\n'
                        return

                    msg_id = f"msg_{log_id}"
                    yield f'data: {{"type":"message_start","message":{{"id":"{msg_id}","type":"message","role":"assistant","content":[],"model":"{model}","stop_reason":null,"stop_sequence":null,"usage":{{"input_tokens":0,"output_tokens":0}}}}}}\n\n'
                    yield f'data: {{"type":"content_block_start","index":0,"content_block":{{"type":"text","text":""}}}}\n\n'

                    full_response = b""

                    async for chunk in response.aiter_bytes():
                        full_response += chunk

                        try:
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
                                        content = None
                                        if 'assistantResponseEvent' in payload:
                                            content = payload['assistantResponseEvent'].get('content')
                                        elif 'content' in payload:
                                            content = payload['content']
                                        if content:
                                            yield f'data: {{"type":"content_block_delta","index":0,"delta":{{"type":"text_delta","text":{json.dumps(content)}}}}}\n\n'
                                    except Exception:
                                        pass
                                pos += total_len
                        except Exception:
                            pass

                    result = parse_event_stream_full(full_response)

                    yield f'data: {{"type":"content_block_stop","index":0}}\n\n'

                    if result["tool_uses"]:
                        for i, tool_use in enumerate(result["tool_uses"], 1):
                            yield f'data: {{"type":"content_block_start","index":{i},"content_block":{{"type":"tool_use","id":"{tool_use["id"]}","name":"{tool_use["name"]}","input":{{}}}}}}\n\n'
                            yield f'data: {{"type":"content_block_delta","index":{i},"delta":{{"type":"input_json_delta","partial_json":{json.dumps(json.dumps(tool_use["input"]))}}}}}\n\n'
                            yield f'data: {{"type":"content_block_stop","index":{i}}}\n\n'

                    stop_reason = result["stop_reason"]
                    yield f'data: {{"type":"message_delta","delta":{{"stop_reason":"{stop_reason}","stop_sequence":null}},"usage":{{"output_tokens":100}}}}\n\n'
                    yield f'data: {{"type":"message_stop"}}\n\n'

                    account.request_count += 1
                    account.last_used = time.time()

        except Exception as e:
            yield f'data: {{"type":"error","error":{{"type":"api_error","message":"{str(e)}"}}}}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _handle_non_stream(kiro_request, headers, account, model, log_id, start_time):
    """Handle non-streaming responses."""
    error_msg = None
    status_code = 200

    try:
        async with httpx.AsyncClient(verify=False, timeout=300) as client:
            response = await client.post(KIRO_API_URL, json=kiro_request, headers=headers)
            status_code = response.status_code

            if response.status_code == 429:
                state.mark_rate_limited(account.id)
                raise HTTPException(429, "Rate limited")

            if response.status_code != 200:
                error_msg = response.text
                status, _, error_message = _classify_kiro_error(error_msg)
                raise HTTPException(status, error_message)

            result = parse_event_stream_full(response.content)
            account.request_count += 1
            account.last_used = time.time()

            return convert_kiro_response_to_anthropic(result, model, f"msg_{log_id}")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        status_code = 500
        raise HTTPException(500, str(e))
    finally:
        duration = (time.time() - start_time) * 1000
        state.add_log(RequestLog(
            id=log_id,
            timestamp=time.time(),
            method="POST",
            path="/v1/messages",
            model=model,
            account_id=account.id if account else None,
            status=status_code,
            duration_ms=duration,
            error=error_msg
        ))
