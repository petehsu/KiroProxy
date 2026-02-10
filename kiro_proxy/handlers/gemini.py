"""Gemini 协议处理 - /v1/models/{model}:generateContent"""
import json
import uuid
import time
import hashlib
import asyncio
import httpx
from fastapi import Request, HTTPException

from ..config import KIRO_API_URL, map_model_name
from ..core import state, is_retryable_error
from ..core.state import RequestLog
from ..core.history_manager import HistoryManager, get_history_config, is_content_length_error
from ..core.error_handler import classify_error, ErrorType, format_error_log
from ..core.rate_limiter import get_rate_limiter
from ..kiro_api import build_headers, build_kiro_request, parse_event_stream, parse_event_stream_full, is_quota_exceeded_error
from ..converters import convert_gemini_contents_to_kiro, convert_kiro_response_to_gemini, convert_gemini_tools_to_kiro


async def handle_generate_content(model_name: str, request: Request):
    """处理 Gemini generateContent 请求"""
    start_time = time.time()
    log_id = uuid.uuid4().hex[:8]
    
    body = await request.json()
    contents = body.get("contents", [])
    system_instruction = body.get("systemInstruction", {})
    tools = body.get("tools", [])
    tool_config = body.get("toolConfig", {})
    
    model_raw = model_name.replace("models/", "")
    model = map_model_name(model_raw)
    
    session_id = hashlib.sha256(json.dumps(contents[:3], sort_keys=True).encode()).hexdigest()[:16]
    account = state.get_available_account(session_id)
    
    if not account:
        raise HTTPException(503, "All accounts are rate limited")
    
    # 检查 token 是否即将过期
    if account.is_token_expiring_soon(5):
        print(f"[Gemini] Token 即将过期，尝试刷新: {account.id}")
        success, msg = await account.refresh_token()
        if not success:
            print(f"[Gemini] Token 刷新失败: {msg}")
    
    token = account.get_token()
    if not token:
        raise HTTPException(500, f"Failed to get token for account {account.name}")
    
    # 构建 headers（提前构建，供摘要使用）
    creds = account.get_credentials()
    headers = build_headers(
        token,
        machine_id=account.get_machine_id(),
        profile_arn=creds.profile_arn if creds else None,
        client_id=creds.client_id if creds else None
    )
    
    # 限速检查
    rate_limiter = get_rate_limiter()
    can_request, wait_seconds, reason = rate_limiter.can_request(account.id)
    if not can_request:
        print(f"[Gemini] 限速: {reason}")
        await asyncio.sleep(wait_seconds)
    
    # 转换消息格式
    user_content, history, tool_results, kiro_tools = convert_gemini_contents_to_kiro(
        contents, system_instruction, model, tools, tool_config
    )
    
    # 历史消息预处理
    history_manager = HistoryManager(get_history_config(), cache_key=session_id)
    
    async def call_summary(prompt: str) -> str:
        req = build_kiro_request(prompt, "claude-haiku-4.5", [])
        try:
            async with httpx.AsyncClient(verify=False, timeout=60) as client:
                resp = await client.post(KIRO_API_URL, json=req, headers=headers)
                if resp.status_code == 200:
                    return parse_event_stream(resp.content)
        except Exception as e:
            print(f"[Summary] API 调用失败: {e}")
        return ""

    # 检查是否需要智能摘要或错误重试预摘要
    if history_manager.should_summarize(history) or history_manager.should_pre_summary_for_error_retry(history, user_content):
        history = await history_manager.pre_process_async(history, user_content, call_summary)
    else:
        history = history_manager.pre_process(history, user_content)
    
    # 摘要/截断后再次修复历史交替和 toolUses/toolResults 配对
    from ..converters import fix_history_alternation
    history = fix_history_alternation(history)
    
    if history_manager.was_truncated:
        print(f"[Gemini] {history_manager.truncate_info}")

    async def call_summary(prompt: str) -> str:
        req = build_kiro_request(prompt, "claude-haiku-4.5", [])
        try:
            async with httpx.AsyncClient(verify=False, timeout=60) as client:
                resp = await client.post(KIRO_API_URL, json=req, headers=headers)
                if resp.status_code == 200:
                    return parse_event_stream(resp.content)
        except Exception as e:
            print(f"[Summary] API 调用失败: {e}")
        return ""
    
    # 构建 Kiro 请求
    kiro_request = build_kiro_request(
        user_content, model, history,
        tools=kiro_tools if kiro_tools else None,
        tool_results=tool_results if tool_results else None
    )
    
    error_msg = None
    status_code = 200
    content = ""
    current_account = account
    max_retries = 2

    try:
      for retry in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(verify=False, timeout=120) as client:
                resp = await client.post(KIRO_API_URL, json=kiro_request, headers=headers)
                status_code = resp.status_code
                
                # 处理配额超限
                if resp.status_code == 429 or is_quota_exceeded_error(resp.status_code, resp.text):
                    current_account.mark_quota_exceeded("Rate limited")
                    next_account = state.get_next_available_account(current_account.id)
                    if next_account and retry < max_retries:
                        print(f"[Gemini] 配额超限，切换账号: {current_account.id} -> {next_account.id}")
                        current_account = next_account
                        token = current_account.get_token()
                        creds = current_account.get_credentials()
                        headers = build_headers(
                            token,
                            machine_id=current_account.get_machine_id(),
                            profile_arn=creds.profile_arn if creds else None,
                            client_id=creds.client_id if creds else None
                        )
                        continue
                    raise HTTPException(429, "All accounts rate limited")
                
                # 处理可重试的服务端错误
                if is_retryable_error(resp.status_code):
                    if retry < max_retries:
                        print(f"[Gemini] 服务端错误 {resp.status_code}，重试 {retry + 1}/{max_retries}")
                        import asyncio
                        await asyncio.sleep(0.5 * (2 ** retry))
                        continue
                    raise HTTPException(resp.status_code, f"Server error after {max_retries} retries")
                
                if resp.status_code != 200:
                    error_msg = resp.text
                    
                    # 使用统一的错误处理
                    error = classify_error(resp.status_code, error_msg)
                    print(format_error_log(error, current_account.id))
                    
                    # 账号封禁 - 禁用账号
                    if error.should_disable_account:
                        current_account.enabled = False
                        from ..credential import CredentialStatus
                        current_account.status = CredentialStatus.SUSPENDED
                        print(f"[Gemini] 账号 {current_account.id} 已被禁用 (封禁)")
                    
                    # 配额超限 - 标记冷却
                    if error.type == ErrorType.RATE_LIMITED:
                        current_account.mark_quota_exceeded(error_msg[:100])
                    
                    # 尝试切换账号
                    if error.should_switch_account:
                        next_account = state.get_next_available_account(current_account.id)
                        if next_account and retry < max_retries:
                            print(f"[Gemini] 切换账号: {current_account.id} -> {next_account.id}")
                            current_account = next_account
                            headers["Authorization"] = f"Bearer {current_account.get_token()}"
                            continue
                    
                    # 检查是否为内容长度超限错误
                    if error.type == ErrorType.CONTENT_TOO_LONG:
                        history_chars, user_chars, total_chars = history_manager.estimate_request_chars(
                            history, user_content
                        )
                        print(f"[Gemini] 内容长度超限: history={history_chars} chars, user={user_chars} chars, total={total_chars} chars")
                        truncated_history, should_retry = await history_manager.handle_length_error_async(
                            history, retry, call_summary
                        )
                        if should_retry:
                            print(f"[Gemini] 内容长度超限，{history_manager.truncate_info}")
                            history = truncated_history
                            kiro_request = build_kiro_request(
                                user_content, model, history,
                                tools=kiro_tools if kiro_tools else None,
                                tool_results=tool_results if tool_results else None
                            )
                            continue
                        else:
                            print(f"[Gemini] 内容长度超限但未重试: retry={retry}/{max_retries}")
                    
                    raise HTTPException(resp.status_code, error.user_message)
                
                # 使用完整解析以支持工具调用
                result = parse_event_stream_full(resp.content)
                current_account.request_count += 1
                current_account.last_used = time.time()
                get_rate_limiter().record_request(current_account.id)
                break
                
        except HTTPException:
            raise
        except httpx.TimeoutException:
            error_msg = "Request timeout"
            status_code = 408
            if retry < max_retries:
                print(f"[Gemini] 请求超时，重试 {retry + 1}/{max_retries}")
                import asyncio
                await asyncio.sleep(0.5 * (2 ** retry))
                continue
            raise HTTPException(408, "Request timeout after retries")
        except httpx.ConnectError:
            error_msg = "Connection error"
            status_code = 502
            if retry < max_retries:
                print(f"[Gemini] 连接错误，重试 {retry + 1}/{max_retries}")
                import asyncio
                await asyncio.sleep(0.5 * (2 ** retry))
                continue
            raise HTTPException(502, "Connection error after retries")
        except Exception as e:
            error_msg = str(e)
            status_code = 500
            if is_retryable_error(None, e) and retry < max_retries:
                print(f"[Gemini] 网络错误，重试 {retry + 1}/{max_retries}: {type(e).__name__}")
                import asyncio
                await asyncio.sleep(0.5 * (2 ** retry))
                continue
            raise HTTPException(500, str(e))
    finally:
        # 记录日志
        duration = (time.time() - start_time) * 1000
        state.add_log(RequestLog(
            id=log_id,
            timestamp=time.time(),
            method="POST",
            path=f"/v1/models/{model_name}:generateContent",
            model=model,
            account_id=current_account.id if current_account else None,
            status=status_code,
            duration_ms=duration,
            error=error_msg
        ))
    
    # 使用转换函数生成 Gemini 格式响应
    return convert_kiro_response_to_gemini(result, model)
