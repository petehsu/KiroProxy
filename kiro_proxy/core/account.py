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
    proxy_url: Optional[str] = None  # Per-account proxy URL (HTTP/SOCKS5)
    
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
        return True
    
    def load_credentials(self) -> Optional[KiroCredentials]:
        """加载凭证信息"""
        try:
            self._credentials = KiroCredentials.load_merged_from_cache(self.token_path)
            
            if (
                self._credentials.client_id_hash
                and (not self._credentials.client_id or not self._credentials.client_secret)
            ):
                self._merge_client_credentials()

            # 凭证刷新后，machine_id 需要重算
            self._machine_id = None
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
            self._machine_id = generate_machine_id(
                profile_arn=creds.profile_arn,
                client_id=creds.client_id,
                uuid=creds.uuid,
            )
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
        
        refresher = TokenRefresher(creds, proxy_url=self.get_proxy_url())
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
    
    def get_proxy_url(self) -> Optional[str]:
        """Get normalized proxy URL for this account.

        Returns per-account proxy if set, otherwise None (caller
        should fall back to the global proxy).
        """
        url = (self.proxy_url or "").strip()
        if not url:
            return None
        if not url.startswith(("http://", "https://", "socks5://", "socks4://")):
            url = f"http://{url}"
        return url

    def get_status_info(self) -> dict:
        """获取状态信息"""
        cooldown_remaining = quota_manager.get_cooldown_remaining(self.id)
        creds = self.get_credentials()
        
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "status": self.status.value,
            "available": self.is_available(),
            "request_count": self.request_count,
            "error_count": self.error_count,
            "cooldown_remaining": cooldown_remaining,
            "token_expired": self.is_token_expired() if creds else None,
            "token_expiring_soon": self.is_token_expiring_soon() if creds else None,
            "auth_method": creds.auth_method if creds else None,
            "has_refresh_token": bool(creds and creds.refresh_token),
            "idc_config_complete": bool(creds and creds.client_id and creds.client_secret) if creds and creds.auth_method == "idc" else None,
            "proxy_url": self.proxy_url or None,
        }
