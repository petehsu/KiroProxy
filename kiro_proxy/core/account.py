"""账号管理"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..credential import (
    KiroCredentials, TokenRefresher, CredentialStatus,
    generate_machine_id, quota_manager
)


@dataclass
class Account:
    """账号信息"""
    id: str
    name: str
    token_path: str
    enabled: bool = True
    request_count: int = 0
    error_count: int = 0
    last_used: Optional[float] = None
    status: CredentialStatus = CredentialStatus.ACTIVE
    
    _credentials: Optional[KiroCredentials] = field(default=None, repr=False)
    _machine_id: Optional[str] = field(default=None, repr=False)
    
    def is_available(self) -> bool:
        """检查账号是否可用"""
        if not self.enabled:
            return False
        if self.status in (CredentialStatus.DISABLED, CredentialStatus.UNHEALTHY, CredentialStatus.SUSPENDED):
            return False
        if not quota_manager.is_available(self.id):
            return False
        
        # 检查额度是否耗尽
        from .quota_cache import get_quota_cache
        quota_cache = get_quota_cache()
        quota = quota_cache.get(self.id)
        if quota and quota.is_exhausted:
            return False
        
        return True
    
    def is_active(self) -> bool:
        """检查账号是否活跃（最近60秒内使用过）"""
        from .quota_scheduler import get_quota_scheduler
        scheduler = get_quota_scheduler()
        return scheduler.is_active(self.id)
    
    def get_priority_order(self) -> Optional[int]:
        """获取优先级顺序（从1开始），非优先账号返回 None"""
        from .account_selector import get_account_selector
        selector = get_account_selector()
        return selector.get_priority_order(self.id)
    
    def is_priority(self) -> bool:
        """检查是否为优先账号"""
        return self.get_priority_order() is not None
    
    def load_credentials(self) -> Optional[KiroCredentials]:
        """加载凭证信息"""
        try:
            self._credentials = KiroCredentials.from_file(self.token_path)
            
            if self._credentials.client_id_hash and not self._credentials.client_id:
                self._merge_client_credentials()
            
            return self._credentials
        except Exception as e:
            print(f"[Account] 加载凭证失败 {self.id}: {e}")
            return None
    
    def _merge_client_credentials(self):
        """合并 clientIdHash 对应的凭证文件"""
        if not self._credentials or not self._credentials.client_id_hash:
            return
        
        cache_dir = Path(self.token_path).parent
        hash_file = cache_dir / f"{self._credentials.client_id_hash}.json"
        
        if hash_file.exists():
            try:
                with open(hash_file) as f:
                    data = json.load(f)
                if not self._credentials.client_id:
                    self._credentials.client_id = data.get("clientId")
                if not self._credentials.client_secret:
                    self._credentials.client_secret = data.get("clientSecret")
            except Exception:
                pass
    
    def get_credentials(self) -> Optional[KiroCredentials]:
        """获取凭证（带缓存）"""
        if self._credentials is None:
            self.load_credentials()
        return self._credentials
    
    def get_token(self) -> str:
        """获取 access_token"""
        creds = self.get_credentials()
        if creds and creds.access_token:
            return creds.access_token
        
        try:
            with open(self.token_path) as f:
                return json.load(f).get("accessToken", "")
        except Exception:
            return ""
    
    def get_machine_id(self) -> str:
        """获取基于此账号的 Machine ID"""
        if self._machine_id:
            return self._machine_id
        
        creds = self.get_credentials()
        if creds:
            self._machine_id = generate_machine_id(creds.profile_arn, creds.client_id)
        else:
            self._machine_id = generate_machine_id()
        
        return self._machine_id
    
    def is_token_expired(self) -> bool:
        """检查 token 是否过期"""
        creds = self.get_credentials()
        return creds.is_expired() if creds else True
    
    def is_token_expiring_soon(self, minutes: int = 10) -> bool:
        """检查 token 是否即将过期"""
        creds = self.get_credentials()
        return creds.is_expiring_soon(minutes) if creds else False
    
    async def refresh_token(self) -> tuple:
        """刷新 token"""
        creds = self.get_credentials()
        if not creds:
            return False, "无法加载凭证"
        
        refresher = TokenRefresher(creds)
        success, result = await refresher.refresh()
        
        if success:
            creds.save_to_file(self.token_path)
            self._credentials = creds
            self.status = CredentialStatus.ACTIVE
            return True, "Token 刷新成功"
        else:
            self.status = CredentialStatus.UNHEALTHY
            return False, result
    
    def mark_quota_exceeded(self, reason: str = "Rate limited"):
        """标记配额超限（只在限速启用时生效）"""
        from .rate_limiter import get_rate_limiter
        rate_limiter = get_rate_limiter()
        
        if rate_limiter.should_apply_quota_cooldown():
            # 使用限速器配置的冷却时间
            cooldown = rate_limiter.get_quota_cooldown_seconds()
            quota_manager.mark_exceeded(self.id, reason, cooldown_seconds=cooldown)
            self.status = CredentialStatus.COOLDOWN
            self.error_count += 1
        # 如果限速未启用，不标记冷却，只记录错误
        else:
            self.error_count += 1
    
    def get_status_info(self) -> dict:
        """获取状态信息"""
        cooldown_remaining = quota_manager.get_cooldown_remaining(self.id)
        creds = self.get_credentials()
        
        # 获取额度信息
        from .quota_cache import get_quota_cache
        quota_cache = get_quota_cache()
        quota = quota_cache.get(self.id)
        
        quota_info = None
        if quota:
            # 计算相对时间
            updated_ago = ""
            if quota.updated_at > 0:
                seconds_ago = time.time() - quota.updated_at
                if seconds_ago < 60:
                    updated_ago = f"{int(seconds_ago)}秒前"
                elif seconds_ago < 3600:
                    updated_ago = f"{int(seconds_ago / 60)}分钟前"
                else:
                    updated_ago = f"{int(seconds_ago / 3600)}小时前"
            
            quota_info = {
                "balance": quota.balance,
                "usage_limit": quota.usage_limit,
                "current_usage": quota.current_usage,
                "usage_percent": quota.usage_percent,
                "is_low_balance": quota.is_low_balance,
                "is_exhausted": quota.is_exhausted,  # 额度是否耗尽
                "balance_status": quota.balance_status,  # 额度状态: normal, low, exhausted
                "subscription_title": quota.subscription_title,
                "free_trial_limit": quota.free_trial_limit,
                "free_trial_usage": quota.free_trial_usage,
                "bonus_limit": quota.bonus_limit,
                "bonus_usage": quota.bonus_usage,
                "updated_at": updated_ago,
                "updated_timestamp": quota.updated_at,
                "error": quota.error
            }
        
        # 计算最后使用时间
        last_used_ago = None
        if self.last_used:
            seconds_ago = time.time() - self.last_used
            if seconds_ago < 60:
                last_used_ago = f"{int(seconds_ago)}秒前"
            elif seconds_ago < 3600:
                last_used_ago = f"{int(seconds_ago / 60)}分钟前"
            else:
                last_used_ago = f"{int(seconds_ago / 3600)}小时前"
        
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "status": self.status.value,
            "available": self.is_available(),
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": f"{(self.error_count / max(1, self.request_count) * 100):.1f}%",
            "cooldown_remaining": cooldown_remaining,
            "token_expired": self.is_token_expired() if creds else None,
            "token_expiring_soon": self.is_token_expiring_soon() if creds else None,
            "token_expires_at": creds.expires_at if creds else None,  # Token 过期时间戳
            "auth_method": creds.auth_method if creds else None,
            "has_refresh_token": bool(creds and creds.refresh_token),
            "idc_config_complete": bool(creds and creds.client_id and creds.client_secret) if creds and creds.auth_method == "idc" else None,
            # 新增字段
            "quota": quota_info,
            "is_priority": self.is_priority(),
            "priority_order": self.get_priority_order(),
            "is_active": self.is_active(),
            "last_used": self.last_used,
            "last_used_ago": last_used_ago,
        }
