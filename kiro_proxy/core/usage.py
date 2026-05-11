"""Kiro 用量查询服务

通过调用 AWS Q 的 getUsageLimits API 获取用户的用量信息。
"""
import uuid
import httpx
from dataclasses import dataclass
from typing import Optional, Tuple

from ..http_client import get_httpx_verify_setting, create_async_client


# API 端点
USAGE_LIMITS_URL = "https://q.us-east-1.amazonaws.com/getUsageLimits"

# 低余额阈值 (20%)
LOW_BALANCE_THRESHOLD = 0.2


@dataclass
class UsageInfo:
    """用量信息"""
    subscription_title: str = ""
    usage_limit: float = 0.0
    current_usage: float = 0.0
    balance: float = 0.0
    is_low_balance: bool = False
    
    # 详细信息
    free_trial_limit: float = 0.0
    free_trial_usage: float = 0.0
    bonus_limit: float = 0.0
    bonus_usage: float = 0.0


def build_usage_api_url(auth_method: str, profile_arn: Optional[str] = None) -> str:
    """构造 API 请求 URL"""
    url = f"{USAGE_LIMITS_URL}?origin=AI_EDITOR&resourceType=AGENTIC_REQUEST"
    
    # Social 认证需要 profileArn
    if auth_method == "social" and profile_arn:
        from urllib.parse import quote
        url += f"&profileArn={quote(profile_arn)}"
    
    return url


def build_usage_headers(
    access_token: str,
    machine_id: str,
    kiro_version: str = "1.0.0"
) -> dict:
    """构造请求头"""
    import platform
    os_name = platform.system().lower()
    
    return {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": f"aws-sdk-js/1.0.0 ua/2.1 os/{os_name} lang/python api/codewhispererruntime#1.0.0 m/N,E KiroIDE-{kiro_version}-{machine_id}",
        "x-amz-user-agent": f"aws-sdk-js/1.0.0 KiroIDE-{kiro_version}-{machine_id}",
        "amz-sdk-invocation-id": str(uuid.uuid4()),
        "amz-sdk-request": "attempt=1; max=1",
        "Connection": "close",
    }


def calculate_balance(response: dict) -> UsageInfo:
    """从 API 响应计算余额"""
    subscription_info = response.get("subscriptionInfo", {})
    usage_breakdown_list = response.get("usageBreakdownList", [])
    
    total_limit = 0.0
    total_usage = 0.0
    free_trial_limit = 0.0
    free_trial_usage = 0.0
    bonus_limit = 0.0
    bonus_usage = 0.0
    
    for breakdown in usage_breakdown_list:
        # 基本额度
        total_limit += breakdown.get("usageLimitWithPrecision", 0.0)
        total_usage += breakdown.get("currentUsageWithPrecision", 0.0)
        
        # 免费试用额度
        free_trial = breakdown.get("freeTrialInfo")
        if free_trial:
            ft_limit = free_trial.get("usageLimitWithPrecision", 0.0)
            ft_usage = free_trial.get("currentUsageWithPrecision", 0.0)
            total_limit += ft_limit
            total_usage += ft_usage
            free_trial_limit += ft_limit
            free_trial_usage += ft_usage
        
        # 奖励额度
        bonuses = breakdown.get("bonuses", [])
        for bonus in bonuses or []:
            b_limit = bonus.get("usageLimit", 0.0)
            b_usage = bonus.get("currentUsage", 0.0)
            total_limit += b_limit
            total_usage += b_usage
            bonus_limit += b_limit
            bonus_usage += b_usage
    
    balance = total_limit - total_usage
    is_low = (balance / total_limit) < LOW_BALANCE_THRESHOLD if total_limit > 0 else False
    
    return UsageInfo(
        subscription_title=subscription_info.get("subscriptionTitle", "Unknown"),
        usage_limit=total_limit,
        current_usage=total_usage,
        balance=balance,
        is_low_balance=is_low,
        free_trial_limit=free_trial_limit,
        free_trial_usage=free_trial_usage,
        bonus_limit=bonus_limit,
        bonus_usage=bonus_usage,
    )


async def get_usage_limits(
    access_token: str,
    auth_method: str = "social",
    profile_arn: Optional[str] = None,
    machine_id: str = "",
    kiro_version: str = "1.0.0",
    proxy_url: Optional[str] = None,
) -> Tuple[bool, UsageInfo | dict]:
    """
    获取 Kiro 用量信息
    
    Args:
        access_token: Bearer token
        auth_method: 认证方式 ("social" 或 "idc")
        profile_arn: Social 认证需要的 profileArn
        machine_id: 设备 ID
        kiro_version: Kiro 版本号
    
    Returns:
        (success, UsageInfo or error_dict)
    """
    if not access_token:
        return False, {"error": "缺少 access token"}
    
    if not machine_id:
        return False, {"error": "缺少 machine ID"}
    
    # 构造 URL 和请求头
    url = build_usage_api_url(auth_method, profile_arn)
    headers = build_usage_headers(access_token, machine_id, kiro_version)
    
    try:
        async with create_async_client(timeout=10, account_proxy_url=proxy_url) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                return False, {"error": f"API 请求失败: {response.status_code} - {response.text[:200]}"}
            
            data = response.json()
            usage_info = calculate_balance(data)
            return True, usage_info
            
    except httpx.TimeoutException:
        return False, {"error": "请求超时"}
    except Exception as e:
        return False, {"error": f"请求失败: {str(e)}"}


async def get_account_usage(account) -> Tuple[bool, UsageInfo | dict]:
    """
    获取指定账号的用量信息
    
    Args:
        account: Account 对象
    
    Returns:
        (success, UsageInfo or error_dict)
    """
    from ..credential import get_kiro_version
    
    token = account.get_token()
    if not token:
        return False, {"error": "无法获取 token"}
    
    creds = account.get_credentials()
    if not creds:
        return False, {"error": "无法获取凭证"}
    
    return await get_usage_limits(
        access_token=token,
        auth_method=creds.auth_method or "social",
        profile_arn=creds.profile_arn,
        machine_id=account.get_machine_id(),
        kiro_version=get_kiro_version(),
        proxy_url=account.get_proxy_url(),
    )
