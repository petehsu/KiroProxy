"""错误处理模块 - 统一的错误分类和处理

检测各种 Kiro API 错误类型：
- 账号封禁 (TEMPORARILY_SUSPENDED)
- 配额超限 (Rate Limit)
- 内容过长 (CONTENT_LENGTH_EXCEEDS_THRESHOLD)
- 认证失败 (Unauthorized)
- 服务不可用 (Service Unavailable)
"""
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple


class ErrorType(str, Enum):
    """错误类型"""
    ACCOUNT_SUSPENDED = "account_suspended"      # 账号被封禁
    RATE_LIMITED = "rate_limited"                # 配额超限
    CONTENT_TOO_LONG = "content_too_long"        # 内容过长
    AUTH_FAILED = "auth_failed"                  # 认证失败
    SERVICE_UNAVAILABLE = "service_unavailable"  # 服务不可用
    MODEL_UNAVAILABLE = "model_unavailable"      # 模型不可用
    UNKNOWN = "unknown"                          # 未知错误


@dataclass
class KiroError:
    """Kiro API 错误"""
    type: ErrorType
    status_code: int
    message: str
    user_message: str  # 用户友好的消息
    should_disable_account: bool = False  # 是否应该禁用账号
    should_switch_account: bool = False   # 是否应该切换账号
    should_retry: bool = False            # 是否应该重试
    cooldown_seconds: int = 0             # 冷却时间


def classify_error(status_code: int, error_text: str) -> KiroError:
    """分类 Kiro API 错误
    
    Args:
        status_code: HTTP 状态码
        error_text: 错误响应文本
    
    Returns:
        KiroError 对象
    """
    error_lower = error_text.lower()
    
    # 1. 账号封禁检测 (最严重)
    if "temporarily_suspended" in error_lower or "suspended" in error_lower:
        # 提取 User ID
        user_id_match = re.search(r'User ID \(([^)]+)\)', error_text)
        user_id = user_id_match.group(1) if user_id_match else "unknown"
        
        return KiroError(
            type=ErrorType.ACCOUNT_SUSPENDED,
            status_code=status_code,
            message=error_text,
            user_message=f"⚠️ 账号已被封禁 (User ID: {user_id})。请联系 AWS 支持解封: https://support.aws.amazon.com/#/contacts/kiro",
            should_disable_account=True,
            should_switch_account=True,
        )
    
    # 2. 402 Payment Required - 额度用尽
    if status_code == 402 or "payment required" in error_lower or "insufficient" in error_lower:
        return KiroError(
            type=ErrorType.RATE_LIMITED,
            status_code=status_code,
            message=error_text,
            user_message="账号额度已用尽，已切换到其他账号",
            should_switch_account=True,
            cooldown_seconds=3600,  # 额度用尽冷却 1 小时
        )
    
    # 3. 配额超限检测 (429)
    quota_keywords = ["rate limit", "quota", "too many requests", "throttl", "capacity"]
    if status_code == 429 or any(kw in error_lower for kw in quota_keywords):
        return KiroError(
            type=ErrorType.RATE_LIMITED,
            status_code=status_code,
            message=error_text,
            user_message="请求过于频繁，账号已进入冷却期",
            should_switch_account=True,
            cooldown_seconds=300,
        )
    
    # 4. 内容过长检测
    if "content_length_exceeds_threshold" in error_lower or (
        "too long" in error_lower and ("input" in error_lower or "content" in error_lower)
    ):
        return KiroError(
            type=ErrorType.CONTENT_TOO_LONG,
            status_code=status_code,
            message=error_text,
            user_message="对话历史过长，请使用 /clear 清空对话",
            should_retry=True,
        )
    
    # 5. 认证失败检测
    if status_code == 401 or "unauthorized" in error_lower or "invalid token" in error_lower:
        return KiroError(
            type=ErrorType.AUTH_FAILED,
            status_code=status_code,
            message=error_text,
            user_message="Token 已过期或无效，请刷新 Token",
            should_switch_account=True,
        )
    
    # 6. 模型不可用检测
    if "model_temporarily_unavailable" in error_lower or "unexpectedly high load" in error_lower:
        return KiroError(
            type=ErrorType.MODEL_UNAVAILABLE,
            status_code=status_code,
            message=error_text,
            user_message="模型暂时不可用，请稍后重试",
            should_retry=True,
        )
    
    # 7. 服务不可用检测
    if status_code in (502, 503, 504) or "service unavailable" in error_lower:
        return KiroError(
            type=ErrorType.SERVICE_UNAVAILABLE,
            status_code=status_code,
            message=error_text,
            user_message="服务暂时不可用，请稍后重试",
            should_retry=True,
        )
    
    # 8. 未知错误
    return KiroError(
        type=ErrorType.UNKNOWN,
        status_code=status_code,
        message=error_text,
        user_message=f"API 错误 ({status_code})",
    )


def is_account_suspended(status_code: int, error_text: str) -> bool:
    """检查是否为账号封禁错误"""
    error = classify_error(status_code, error_text)
    return error.type == ErrorType.ACCOUNT_SUSPENDED


def get_anthropic_error_response(error: KiroError) -> dict:
    """生成 Anthropic 格式的错误响应"""
    error_type_map = {
        ErrorType.ACCOUNT_SUSPENDED: "authentication_error",
        ErrorType.RATE_LIMITED: "rate_limit_error",
        ErrorType.CONTENT_TOO_LONG: "invalid_request_error",
        ErrorType.AUTH_FAILED: "authentication_error",
        ErrorType.SERVICE_UNAVAILABLE: "api_error",
        ErrorType.MODEL_UNAVAILABLE: "overloaded_error",
        ErrorType.UNKNOWN: "api_error",
    }
    
    return {
        "type": "error",
        "error": {
            "type": error_type_map.get(error.type, "api_error"),
            "message": error.user_message
        }
    }


def format_error_log(error: KiroError, account_id: str = None) -> str:
    """格式化错误日志"""
    lines = [
        f"[{error.type.value.upper()}]",
        f"  Status: {error.status_code}",
        f"  Message: {error.user_message}",
    ]
    if account_id:
        lines.insert(1, f"  Account: {account_id}")
    if error.should_disable_account:
        lines.append("  Action: 账号已被禁用")
    elif error.should_switch_account:
        lines.append("  Action: 切换到其他账号")
    return "\n".join(lines)
