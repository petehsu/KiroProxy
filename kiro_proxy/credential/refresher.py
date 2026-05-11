"""Token 刷新器"""
import httpx
from datetime import datetime, timezone, timedelta
from typing import Tuple

from .types import KiroCredentials
from .fingerprint import generate_machine_id, get_kiro_version
from ..http_client import get_httpx_verify_setting, create_async_client


class TokenRefresher:
    """Token 刷新器"""
    
    def __init__(self, credentials: KiroCredentials, proxy_url: str = None):
        self.credentials = credentials
        self.proxy_url = proxy_url

    def _resolve_auth_method(self) -> str:
        method = (self.credentials.auth_method or "").strip().lower()
        if method in {"idc", "builder-id", "builder_id"}:
            return "idc"
        if method == "social":
            return "social"
        # 兼容旧 token：缺失 authMethod 时按字段推断
        if self.credentials.client_id and self.credentials.client_secret:
            return "idc"
        return "social"
    
    def get_refresh_url(self) -> str:
        """获取刷新 URL"""
        auth_method = self._resolve_auth_method()
        region = (self.credentials.region or "us-east-1").strip()
        idc_region = (self.credentials.idc_region or self.credentials.region or "us-east-1").strip()
        
        if auth_method == "idc":
            return f"https://oidc.{idc_region}.amazonaws.com/token"
        else:
            return f"https://prod.{region}.auth.desktop.kiro.dev/refreshToken"
    
    def validate_refresh_token(self) -> Tuple[bool, str]:
        """验证 refresh_token 有效性"""
        refresh_token = self.credentials.refresh_token
        
        if not refresh_token:
            return False, "缺少 refresh_token"
        
        if len(refresh_token.strip()) == 0:
            return False, "refresh_token 为空"
        
        if len(refresh_token) < 100 or refresh_token.endswith("..."):
            return False, f"refresh_token 已被截断（长度: {len(refresh_token)}）"
        
        return True, ""
    
    def _get_machine_id(self) -> str:
        """获取 Machine ID"""
        return generate_machine_id(
            profile_arn=self.credentials.profile_arn,
            client_id=self.credentials.client_id,
            uuid=getattr(self.credentials, "uuid", None),
        )
    
    async def refresh(self) -> Tuple[bool, str]:
        """刷新 token，返回 (success, new_token_or_error)"""
        is_valid, error = self.validate_refresh_token()
        if not is_valid:
            return False, error
        
        refresh_url = self.get_refresh_url()
        auth_method = self._resolve_auth_method()
        self.credentials.auth_method = auth_method
        
        machine_id = self._get_machine_id()
        kiro_version = get_kiro_version()
        
        try:
            async with create_async_client(timeout=30, account_proxy_url=self.proxy_url) as client:
                if auth_method == "idc":
                    if not self.credentials.client_id or not self.credentials.client_secret:
                        return False, "IdC 认证缺少 client_id 或 client_secret"
                    
                    body = {
                        "refreshToken": self.credentials.refresh_token,
                        "clientId": self.credentials.client_id,
                        "clientSecret": self.credentials.client_secret,
                        "grantType": "refresh_token"
                    }
                    headers = {
                        "Content-Type": "application/json",
                        "x-amz-user-agent": f"aws-sdk-js/3.738.0 KiroIDE-{kiro_version}-{machine_id}",
                        "User-Agent": "node",
                    }
                else:
                    body = {"refreshToken": self.credentials.refresh_token}
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": f"KiroIDE-{kiro_version}-{machine_id}",
                        "Accept": "application/json, text/plain, */*",
                    }
                
                resp = await client.post(refresh_url, json=body, headers=headers)
                
                if resp.status_code != 200:
                    error_text = resp.text
                    if resp.status_code == 401:
                        return False, "凭证已过期或无效，需要重新登录"
                    elif resp.status_code == 429:
                        return False, "请求过于频繁，请稍后重试"
                    else:
                        return False, f"刷新失败: {resp.status_code} - {error_text[:200]}"
                
                try:
                    data = resp.json()
                except Exception:
                    return False, f"刷新响应不是 JSON: {resp.text[:200]}"
                
                new_token = data.get("accessToken") or data.get("access_token")
                if not new_token:
                    return False, "响应中没有 access_token"
                
                # 更新凭证
                self.credentials.access_token = new_token
                
                if rt := data.get("refreshToken") or data.get("refresh_token"):
                    self.credentials.refresh_token = rt
                
                if arn := data.get("profileArn"):
                    self.credentials.profile_arn = arn
                
                if expires_in := data.get("expiresIn") or data.get("expires_in"):
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    self.credentials.expires_at = expires_at.isoformat()
                
                self.credentials.last_refresh = datetime.now(timezone.utc).isoformat()
                
                return True, new_token
                
        except Exception as e:
            return False, f"刷新异常: {str(e)}"
