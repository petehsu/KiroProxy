"""Kiro Device Code Flow 登录

实现 AWS OIDC Device Authorization Flow:
1. 注册 OIDC 客户端 -> 获取 clientId + clientSecret
2. 发起设备授权 -> 获取 deviceCode + userCode + verificationUri
3. 用户在浏览器中输入 userCode 完成授权
4. 轮询 Token -> 获取 accessToken + refreshToken

Social Auth (Google/GitHub):
1. 生成 PKCE code_verifier 和 code_challenge
2. 构建登录 URL，打开浏览器
3. 启动本地回调服务器接收授权码
4. 用授权码交换 Token
"""
import json
import time
import httpx
import secrets
import hashlib
import base64
import asyncio
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
from datetime import datetime, timezone


@dataclass
class DeviceFlowState:
    """设备授权流程状态"""
    client_id: str
    client_secret: str
    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_at: int
    region: str
    started_at: float


@dataclass
class SocialAuthState:
    """Social Auth 登录状态"""
    provider: str  # Google / Github
    code_verifier: str
    code_challenge: str
    oauth_state: str
    expires_at: int
    started_at: float


# 全局登录状态
_login_state: Optional[DeviceFlowState] = None
_social_auth_state: Optional[SocialAuthState] = None
_callback_server = None

# Kiro OIDC 配置
KIRO_START_URL = "https://view.awsapps.com/start"
KIRO_AUTH_ENDPOINT = "https://prod.us-east-1.auth.desktop.kiro.dev"
KIRO_SCOPES = [
    "codewhisperer:completions",
    "codewhisperer:analysis",
    "codewhisperer:conversations",
    "codewhisperer:transformations",
    "codewhisperer:taskassist",
]


def get_login_state() -> Optional[dict]:
    """获取当前登录状态"""
    global _login_state
    if _login_state is None:
        return None
    
    # 检查是否过期
    if time.time() > _login_state.expires_at:
        _login_state = None
        return None
    
    return {
        "user_code": _login_state.user_code,
        "verification_uri": _login_state.verification_uri,
        "expires_in": int(_login_state.expires_at - time.time()),
        "interval": _login_state.interval,
    }


async def start_device_flow(region: str = "us-east-1") -> Tuple[bool, dict]:
    """
    启动设备授权流程
    
    Returns:
        (success, result_or_error)
    """
    global _login_state
    
    oidc_base = f"https://oidc.{region}.amazonaws.com"
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: 注册 OIDC 客户端
        print(f"[DeviceFlow] Step 1: 注册 OIDC 客户端...")
        
        reg_body = {
            "clientName": "Kiro Proxy",
            "clientType": "public",
            "scopes": KIRO_SCOPES,
            "grantTypes": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
            "issuerUrl": KIRO_START_URL
        }
        
        try:
            reg_resp = await client.post(
                f"{oidc_base}/client/register",
                json=reg_body,
                headers={"Content-Type": "application/json"}
            )
        except Exception as e:
            return False, {"error": f"注册客户端请求失败: {e}"}
        
        if reg_resp.status_code != 200:
            return False, {"error": f"注册客户端失败: {reg_resp.text}"}
        
        reg_data = reg_resp.json()
        client_id = reg_data.get("clientId")
        client_secret = reg_data.get("clientSecret")
        
        if not client_id or not client_secret:
            return False, {"error": "注册响应缺少 clientId 或 clientSecret"}
        
        print(f"[DeviceFlow] 客户端注册成功: {client_id[:20]}...")
        
        # Step 2: 发起设备授权
        print(f"[DeviceFlow] Step 2: 发起设备授权...")
        
        auth_body = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "startUrl": KIRO_START_URL
        }
        
        try:
            auth_resp = await client.post(
                f"{oidc_base}/device_authorization",
                json=auth_body,
                headers={"Content-Type": "application/json"}
            )
        except Exception as e:
            return False, {"error": f"设备授权请求失败: {e}"}
        
        if auth_resp.status_code != 200:
            return False, {"error": f"设备授权失败: {auth_resp.text}"}
        
        auth_data = auth_resp.json()
        device_code = auth_data.get("deviceCode")
        user_code = auth_data.get("userCode")
        verification_uri = auth_data.get("verificationUriComplete") or auth_data.get("verificationUri")
        interval = auth_data.get("interval", 5)
        expires_in = auth_data.get("expiresIn", 600)
        
        if not device_code or not user_code or not verification_uri:
            return False, {"error": "设备授权响应缺少必要字段"}
        
        print(f"[DeviceFlow] 设备码获取成功: {user_code}")
        
        # 保存状态
        _login_state = DeviceFlowState(
            client_id=client_id,
            client_secret=client_secret,
            device_code=device_code,
            user_code=user_code,
            verification_uri=verification_uri,
            interval=interval,
            expires_at=int(time.time() + expires_in),
            region=region,
            started_at=time.time()
        )
        
        return True, {
            "user_code": user_code,
            "verification_uri": verification_uri,
            "expires_in": expires_in,
            "interval": interval,
        }


async def poll_device_flow() -> Tuple[bool, dict]:
    """
    轮询设备授权状态
    
    Returns:
        (success, result_or_error)
        - success=True, result={"completed": True, "credentials": {...}} 授权完成
        - success=True, result={"completed": False, "status": "pending"} 等待中
        - success=False, result={"error": "..."} 错误
    """
    global _login_state
    
    if _login_state is None:
        return False, {"error": "没有进行中的登录"}
    
    # 检查是否过期
    if time.time() > _login_state.expires_at:
        _login_state = None
        return False, {"error": "授权已过期，请重新开始"}
    
    oidc_base = f"https://oidc.{_login_state.region}.amazonaws.com"
    
    token_body = {
        "clientId": _login_state.client_id,
        "clientSecret": _login_state.client_secret,
        "grantType": "urn:ietf:params:oauth:grant-type:device_code",
        "deviceCode": _login_state.device_code
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            token_resp = await client.post(
                f"{oidc_base}/token",
                json=token_body,
                headers={"Content-Type": "application/json"}
            )
        except Exception as e:
            return False, {"error": f"Token 请求失败: {e}"}
        
        if token_resp.status_code == 200:
            # 授权成功
            token_data = token_resp.json()
            
            credentials = {
                "accessToken": token_data.get("accessToken"),
                "refreshToken": token_data.get("refreshToken"),
                "expiresAt": datetime.now(timezone.utc).isoformat(),
                "clientId": _login_state.client_id,
                "clientSecret": _login_state.client_secret,
                "region": _login_state.region,
                "authMethod": "idc",
            }
            
            # 计算过期时间
            if expires_in := token_data.get("expiresIn"):
                from datetime import timedelta
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                credentials["expiresAt"] = expires_at.isoformat()
            
            # 清除状态
            _login_state = None
            
            print(f"[DeviceFlow] 授权成功！")
            return True, {"completed": True, "credentials": credentials}
        
        # 检查错误类型
        try:
            error_data = token_resp.json()
            error_code = error_data.get("error", "")
        except:
            error_code = ""
        
        if error_code == "authorization_pending":
            # 用户还未完成授权
            return True, {"completed": False, "status": "pending"}
        elif error_code == "slow_down":
            # 请求太频繁
            return True, {"completed": False, "status": "slow_down"}
        elif error_code == "expired_token":
            _login_state = None
            return False, {"error": "授权已过期，请重新开始"}
        elif error_code == "access_denied":
            _login_state = None
            return False, {"error": "用户拒绝授权"}
        else:
            return False, {"error": f"Token 请求失败: {token_resp.text}"}


def cancel_device_flow() -> bool:
    """取消设备授权流程"""
    global _login_state
    if _login_state is not None:
        _login_state = None
        return True
    return False


async def save_credentials_to_file(credentials: dict, name: str = "kiro-proxy-auth") -> str:
    """
    保存凭证到文件
    
    Returns:
        保存的文件路径
    """
    from ..config import TOKEN_DIR
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    file_path = TOKEN_DIR / f"{name}.json"
    
    with open(file_path, "w") as f:
        json.dump(credentials, f, indent=2)
    
    print(f"[DeviceFlow] 凭证已保存到: {file_path}")
    return str(file_path)


# ==================== Social Auth (Google/GitHub) ====================

def _generate_code_verifier() -> str:
    """生成 PKCE code_verifier"""
    return secrets.token_urlsafe(64)[:128]


def _generate_code_challenge(verifier: str) -> str:
    """生成 PKCE code_challenge (SHA256)"""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


def _generate_oauth_state() -> str:
    """生成 OAuth state"""
    return secrets.token_urlsafe(32)


def get_social_auth_state() -> Optional[dict]:
    """获取当前 Social Auth 状态"""
    global _social_auth_state
    if _social_auth_state is None:
        return None
    
    if time.time() > _social_auth_state.expires_at:
        _social_auth_state = None
        return None
    
    return {
        "provider": _social_auth_state.provider,
        "expires_in": int(_social_auth_state.expires_at - time.time()),
    }


async def start_social_auth(provider: str) -> Tuple[bool, dict]:
    """
    启动 Social Auth 登录 (Google/GitHub)
    
    Args:
        provider: "google" 或 "github"
    
    Returns:
        (success, result_or_error)
    """
    global _social_auth_state
    
    # 验证 provider
    provider_normalized = provider.lower()
    if provider_normalized == "google":
        provider_normalized = "Google"
    elif provider_normalized == "github":
        provider_normalized = "Github"
    else:
        return False, {"error": f"不支持的登录提供商: {provider}"}
    
    print(f"[SocialAuth] 开始 {provider_normalized} 登录流程")
    
    # 生成 PKCE
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)
    oauth_state = _generate_oauth_state()
    
    # 回调地址
    redirect_uri = "http://127.0.0.1:19823/kiro-social-callback"
    
    # 构建登录 URL
    from urllib.parse import urlencode, quote
    login_url = f"{KIRO_AUTH_ENDPOINT}/login?idp={provider_normalized}&redirect_uri={quote(redirect_uri)}&code_challenge={quote(code_challenge)}&code_challenge_method=S256&state={quote(oauth_state)}"
    
    print(f"[SocialAuth] 登录 URL: {login_url}")
    
    # 保存状态（10 分钟过期）
    _social_auth_state = SocialAuthState(
        provider=provider_normalized,
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        oauth_state=oauth_state,
        expires_at=int(time.time() + 600),
        started_at=time.time(),
    )
    
    return True, {
        "login_url": login_url,
        "state": oauth_state,
        "provider": provider_normalized,
    }


async def exchange_social_auth_token(code: str, state: str) -> Tuple[bool, dict]:
    """
    用授权码交换 Token
    
    Args:
        code: 授权码
        state: OAuth state
    
    Returns:
        (success, result_or_error)
    """
    global _social_auth_state
    
    if _social_auth_state is None:
        return False, {"error": "没有进行中的社交登录"}
    
    # 验证 state
    if state != _social_auth_state.oauth_state:
        _social_auth_state = None
        return False, {"error": "OAuth state 不匹配"}
    
    # 检查过期
    if time.time() > _social_auth_state.expires_at:
        _social_auth_state = None
        return False, {"error": "登录已过期，请重新开始"}
    
    print(f"[SocialAuth] 交换 Token...")
    
    # 交换 Token
    token_body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "http://127.0.0.1:19823/kiro-social-callback",
        "code_verifier": _social_auth_state.code_verifier,
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            token_resp = await client.post(
                f"{KIRO_AUTH_ENDPOINT}/oauth/token",
                json=token_body,
                headers={"Content-Type": "application/json"}
            )
        except Exception as e:
            _social_auth_state = None
            return False, {"error": f"Token 请求失败: {e}"}
        
        if token_resp.status_code != 200:
            error_text = token_resp.text
            _social_auth_state = None
            return False, {"error": f"Token 交换失败: {error_text}"}
        
        token_data = token_resp.json()
        
        credentials = {
            "accessToken": token_data.get("access_token"),
            "refreshToken": token_data.get("refresh_token"),
            "expiresAt": datetime.now(timezone.utc).isoformat(),
            "authMethod": "social",
        }
        
        # 计算过期时间
        if expires_in := token_data.get("expires_in"):
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            credentials["expiresAt"] = expires_at.isoformat()
        
        provider = _social_auth_state.provider
        _social_auth_state = None
        
        print(f"[SocialAuth] {provider} 登录成功！")
        return True, {"completed": True, "credentials": credentials, "provider": provider}


def cancel_social_auth() -> bool:
    """取消 Social Auth 登录"""
    global _social_auth_state
    if _social_auth_state is not None:
        _social_auth_state = None
        return True
    return False


# ==================== 回调服务器 ====================

_callback_result = None
_callback_event = None

async def start_callback_server() -> Tuple[bool, dict]:
    """启动本地回调服务器"""
    global _callback_result, _callback_event
    
    from aiohttp import web
    
    _callback_result = None
    _callback_event = asyncio.Event()
    
    async def handle_callback(request):
        global _callback_result
        code = request.query.get("code")
        state = request.query.get("state")
        error = request.query.get("error")
        
        if error:
            _callback_result = {"error": error}
        elif code and state:
            _callback_result = {"code": code, "state": state}
        else:
            _callback_result = {"error": "缺少授权码"}
        
        _callback_event.set()
        
        # 返回成功页面
        html = """
        <html>
        <head><title>登录成功</title></head>
        <body style="font-family:sans-serif;text-align:center;padding:50px">
            <h1>✅ 登录成功</h1>
            <p>您可以关闭此窗口并返回 Kiro Proxy</p>
            <script>setTimeout(()=>window.close(),2000)</script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type="text/html")
    
    app = web.Application()
    app.router.add_get("/kiro-social-callback", handle_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    try:
        site = web.TCPSite(runner, "127.0.0.1", 19823)
        await site.start()
        print("[SocialAuth] 回调服务器已启动: http://127.0.0.1:19823")
        return True, {"port": 19823}
    except Exception as e:
        return False, {"error": f"启动回调服务器失败: {e}"}


async def wait_for_callback(timeout: int = 300) -> Tuple[bool, dict]:
    """等待回调"""
    global _callback_result, _callback_event
    
    if _callback_event is None:
        return False, {"error": "回调服务器未启动"}
    
    try:
        await asyncio.wait_for(_callback_event.wait(), timeout=timeout)
        
        if _callback_result and "code" in _callback_result:
            return True, _callback_result
        elif _callback_result and "error" in _callback_result:
            return False, _callback_result
        else:
            return False, {"error": "未收到有效回调"}
    except asyncio.TimeoutError:
        return False, {"error": "等待回调超时"}
