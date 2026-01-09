"""管理 API 处理"""
import json
import uuid
import time
import httpx
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from fastapi import Request, HTTPException, Query

from ..config import TOKEN_PATH, MODELS_URL
from ..core import state, Account, stats_manager, get_browsers_info, open_url, flow_monitor, get_account_usage
from ..credential import quota_manager, generate_machine_id, get_kiro_version, CredentialStatus
from ..auth import start_device_flow, poll_device_flow, cancel_device_flow, get_login_state, save_credentials_to_file
from ..auth import start_social_auth, exchange_social_auth_token, cancel_social_auth, get_social_auth_state


async def get_status():
    """服务状态"""
    try:
        with open(TOKEN_PATH) as f:
            data = json.load(f)
        return {
            "ok": True,
            "expires": data.get("expiresAt"),
            "stats": state.get_stats()
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "stats": state.get_stats()}


async def get_stats():
    """获取统计信息"""
    return state.get_stats()


async def event_logging_batch(request: Request):
    """接收事件日志批量上报（兼容客户端）"""
    try:
        await request.json()
    except Exception:
        pass
    return {"ok": True}


async def get_logs(limit: int = Query(100, le=1000)):
    """获取请求日志"""
    logs = list(state.request_logs)[-limit:]
    return {
        "logs": [asdict(log) for log in reversed(logs)],
        "total": len(state.request_logs)
    }


async def get_accounts():
    """获取账号列表（增强版）"""
    return {
        "accounts": state.get_accounts_status()
    }


async def get_account_detail(account_id: str):
    """获取账号详细信息"""
    for acc in state.accounts:
        if acc.id == account_id:
            creds = acc.get_credentials()
            return {
                "id": acc.id,
                "name": acc.name,
                "enabled": acc.enabled,
                "status": acc.status.value,
                "available": acc.is_available(),
                "request_count": acc.request_count,
                "error_count": acc.error_count,
                "last_used": acc.last_used,
                "token_path": acc.token_path,
                "machine_id": acc.get_machine_id()[:16] + "...",
                "credentials": {
                    "has_access_token": bool(creds and creds.access_token),
                    "has_refresh_token": bool(creds and creds.refresh_token),
                    "has_client_id": bool(creds and creds.client_id),
                    "auth_method": creds.auth_method if creds else None,
                    "region": creds.region if creds else None,
                    "expires_at": creds.expires_at if creds else None,
                    "is_expired": acc.is_token_expired(),
                    "is_expiring_soon": acc.is_token_expiring_soon(),
                } if creds else None,
                "cooldown": {
                    "is_cooldown": not quota_manager.is_available(acc.id),
                    "remaining_seconds": quota_manager.get_cooldown_remaining(acc.id),
                }
            }
    raise HTTPException(404, "Account not found")


async def add_account(request: Request):
    """添加账号"""
    body = await request.json()
    name = body.get("name", f"账号{len(state.accounts)+1}")
    token_path = body.get("token_path")
    
    if not token_path or not Path(token_path).exists():
        raise HTTPException(400, "Invalid token path")
    
    account = Account(
        id=uuid.uuid4().hex[:8],
        name=name,
        token_path=token_path
    )
    state.accounts.append(account)
    
    # 预加载凭证
    account.load_credentials()
    
    # 保存配置
    state._save_accounts()
    
    return {"ok": True, "account_id": account.id}


async def delete_account(account_id: str):
    """删除账号"""
    state.accounts = [a for a in state.accounts if a.id != account_id]
    # 清理配额记录
    quota_manager.restore(account_id)
    # 保存配置
    state._save_accounts()
    return {"ok": True}


async def toggle_account(account_id: str):
    """启用/禁用账号"""
    for acc in state.accounts:
        if acc.id == account_id:
            acc.enabled = not acc.enabled
            # 保存配置
            state._save_accounts()
            return {"ok": True, "enabled": acc.enabled}
    raise HTTPException(404, "Account not found")


async def refresh_account_token(account_id: str):
    """刷新指定账号的 token"""
    success, message = await state.refresh_account_token(account_id)
    return {"ok": success, "message": message}


async def refresh_all_tokens():
    """刷新所有即将过期的 token"""
    results = await state.refresh_expiring_tokens()
    return {
        "ok": True,
        "results": results,
        "refreshed": len([r for r in results if r["success"]])
    }


async def restore_account(account_id: str):
    """恢复账号（从冷却状态）"""
    restored = quota_manager.restore(account_id)
    if restored:
        for acc in state.accounts:
            if acc.id == account_id:
                from ..credential import CredentialStatus
                acc.status = CredentialStatus.ACTIVE
                break
    return {"ok": restored}


async def speedtest():
    """测试 API 延迟"""
    account = state.get_available_account()
    if not account:
        return {"ok": False, "error": "No available account"}
    
    start = time.time()
    try:
        token = account.get_token()
        machine_id = account.get_machine_id()
        kiro_version = get_kiro_version()
        
        headers = {
            "content-type": "application/json",
            "x-amz-user-agent": f"aws-sdk-js/1.0.0 KiroIDE-{kiro_version}-{machine_id}",
            "Authorization": f"Bearer {token}",
        }
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.get(MODELS_URL, headers=headers, params={"origin": "AI_EDITOR"})
            latency = (time.time() - start) * 1000
            return {
                "ok": resp.status_code == 200,
                "latency_ms": round(latency, 2),
                "status": resp.status_code,
                "account_id": account.id
            }
    except Exception as e:
        return {"ok": False, "error": str(e), "latency_ms": (time.time() - start) * 1000}


async def scan_tokens():
    """扫描系统中的 Kiro token 文件"""
    from ..config import TOKEN_DIR
    
    found = []
    
    # 扫描新目录
    if TOKEN_DIR.exists():
        for f in TOKEN_DIR.glob("*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    if "accessToken" in data:
                        # 检查是否已添加
                        already_added = any(a.token_path == str(f) for a in state.accounts)
                        
                        auth_method = data.get("authMethod", "social")
                        client_id_hash = data.get("clientIdHash")
                        
                        # 检查 IdC 配置完整性
                        idc_complete = None
                        if auth_method == "idc" and client_id_hash:
                            hash_file = TOKEN_DIR / f"{client_id_hash}.json"
                            if hash_file.exists():
                                try:
                                    with open(hash_file) as hf:
                                        hash_data = json.load(hf)
                                        idc_complete = bool(hash_data.get("clientId") and hash_data.get("clientSecret"))
                                except:
                                    idc_complete = False
                            else:
                                idc_complete = False
                        
                        found.append({
                            "path": str(f),
                            "name": f.stem,
                            "expires": data.get("expiresAt"),
                            "auth_method": auth_method,
                            "region": data.get("region", "us-east-1"),
                            "has_refresh_token": "refreshToken" in data,
                            "already_added": already_added,
                            "idc_config_complete": idc_complete,
                        })
            except:
                pass
    
    # 兼容：也扫描旧的 AWS SSO 目录
    sso_cache = Path.home() / ".aws/sso/cache"
    if sso_cache.exists():
        for f in sso_cache.glob("*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    if "accessToken" in data:
                        already_added = any(a.token_path == str(f) for a in state.accounts)
                        auth_method = data.get("authMethod", "social")
                        
                        found.append({
                            "path": str(f),
                            "name": f.stem + " (旧目录)",
                            "expires": data.get("expiresAt"),
                            "auth_method": auth_method,
                            "region": data.get("region", "us-east-1"),
                            "has_refresh_token": "refreshToken" in data,
                            "already_added": already_added,
                            "idc_config_complete": None,
                        })
            except:
                pass
    
    return {"tokens": found}


async def add_from_scan(request: Request):
    """从扫描结果添加账号"""
    body = await request.json()
    token_path = body.get("path")
    name = body.get("name", "扫描账号")
    
    if not token_path or not Path(token_path).exists():
        raise HTTPException(400, "Token 文件不存在")
    
    if any(a.token_path == token_path for a in state.accounts):
        raise HTTPException(400, "该账号已添加")
    
    try:
        with open(token_path) as f:
            data = json.load(f)
            if "accessToken" not in data:
                raise HTTPException(400, "无效的 token 文件")
    except json.JSONDecodeError:
        raise HTTPException(400, "无效的 JSON 文件")
    
    account = Account(
        id=uuid.uuid4().hex[:8],
        name=name,
        token_path=token_path
    )
    state.accounts.append(account)
    
    # 预加载凭证
    account.load_credentials()
    
    # 保存配置
    state._save_accounts()
    
    return {"ok": True, "account_id": account.id}


async def export_config():
    """导出配置"""
    return {
        "accounts": [
            {"name": a.name, "token_path": a.token_path, "enabled": a.enabled}
            for a in state.accounts
        ],
        "exported_at": datetime.now().isoformat()
    }


async def import_config(request: Request):
    """导入配置"""
    body = await request.json()
    accounts = body.get("accounts", [])
    imported = 0
    
    for acc_data in accounts:
        token_path = acc_data.get("token_path", "")
        if Path(token_path).exists():
            if not any(a.token_path == token_path for a in state.accounts):
                account = Account(
                    id=uuid.uuid4().hex[:8],
                    name=acc_data.get("name", "导入账号"),
                    token_path=token_path,
                    enabled=acc_data.get("enabled", True)
                )
                state.accounts.append(account)
                account.load_credentials()
                imported += 1
    
    # 保存配置
    state._save_accounts()
    
    return {"ok": True, "imported": imported}


async def refresh_token_check():
    """检查所有账号的 token 状态"""
    results = []
    for acc in state.accounts:
        creds = acc.get_credentials()
        if creds:
            results.append({
                "id": acc.id,
                "name": acc.name,
                "valid": not acc.is_token_expired(),
                "expiring_soon": acc.is_token_expiring_soon(),
                "expires": creds.expires_at,
                "auth_method": creds.auth_method,
                "has_refresh_token": bool(creds.refresh_token),
            })
        else:
            results.append({
                "id": acc.id,
                "name": acc.name,
                "valid": False,
                "error": "无法加载凭证"
            })
    
    return {"accounts": results}


async def get_quota_status():
    """获取配额状态"""
    return {
        "cooldown_seconds": quota_manager.cooldown_seconds,
        "exceeded_count": len(quota_manager.exceeded_records),
        "exceeded_credentials": [
            {
                "credential_id": r.credential_id,
                "exceeded_at": r.exceeded_at,
                "cooldown_until": r.cooldown_until,
                "remaining_seconds": max(0, int(r.cooldown_until - time.time())),
                "reason": r.reason
            }
            for r in quota_manager.exceeded_records.values()
        ]
    }


async def get_kiro_login_url():
    """获取 Kiro 登录说明"""
    from ..config import TOKEN_DIR
    return {
        "message": "请使用本代理的登录功能，或从 Kiro IDE 导入 token",
        "instructions": [
            "1. 点击「添加」按钮，选择登录方式",
            "2. 或者从 Kiro IDE 的 ~/.aws/sso/cache/ 复制 token 文件",
            "3. 将 token 文件放到 ~/.kiro-proxy/tokens/ 目录",
            "4. 点击「扫描」按钮自动识别"
        ],
        "token_dir": str(TOKEN_DIR),
        "token_dir_exists": TOKEN_DIR.exists()
    }


async def get_detailed_stats():
    """获取详细统计信息"""
    basic_stats = state.get_stats()
    detailed = stats_manager.get_all_stats()
    
    return {
        **basic_stats,
        "detailed": detailed
    }


async def run_health_check():
    """手动触发健康检查"""
    results = []
    
    for acc in state.accounts:
        if not acc.enabled:
            results.append({
                "id": acc.id,
                "name": acc.name,
                "status": "disabled",
                "healthy": False
            })
            continue
        
        try:
            token = acc.get_token()
            if not token:
                acc.status = CredentialStatus.UNHEALTHY
                results.append({
                    "id": acc.id,
                    "name": acc.name,
                    "status": "no_token",
                    "healthy": False
                })
                continue
            
            headers = {
                "Authorization": f"Bearer {token}",
                "content-type": "application/json"
            }
            
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(
                    MODELS_URL,
                    headers=headers,
                    params={"origin": "AI_EDITOR"}
                )
                
                if resp.status_code == 200:
                    if acc.status == CredentialStatus.UNHEALTHY:
                        acc.status = CredentialStatus.ACTIVE
                    results.append({
                        "id": acc.id,
                        "name": acc.name,
                        "status": "healthy",
                        "healthy": True,
                        "latency_ms": resp.elapsed.total_seconds() * 1000
                    })
                elif resp.status_code == 401:
                    acc.status = CredentialStatus.UNHEALTHY
                    results.append({
                        "id": acc.id,
                        "name": acc.name,
                        "status": "auth_failed",
                        "healthy": False
                    })
                elif resp.status_code == 429:
                    results.append({
                        "id": acc.id,
                        "name": acc.name,
                        "status": "rate_limited",
                        "healthy": True  # 限流不代表不健康
                    })
                else:
                    results.append({
                        "id": acc.id,
                        "name": acc.name,
                        "status": f"error_{resp.status_code}",
                        "healthy": False
                    })
                    
        except Exception as e:
            results.append({
                "id": acc.id,
                "name": acc.name,
                "status": "error",
                "healthy": False,
                "error": str(e)
            })
    
    healthy_count = len([r for r in results if r["healthy"]])
    return {
        "ok": True,
        "total": len(results),
        "healthy": healthy_count,
        "unhealthy": len(results) - healthy_count,
        "results": results
    }


# ==================== Kiro 登录 API ====================

async def get_browsers():
    """获取可用浏览器列表"""
    return {"browsers": get_browsers_info()}


async def start_kiro_login(request: Request):
    """启动 Kiro 设备授权登录"""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    region = body.get("region", "us-east-1")
    browser = body.get("browser", "default")
    incognito = body.get("incognito", False)
    
    success, result = await start_device_flow(region)
    
    if success:
        # 用指定浏览器打开授权页面
        open_url(result["verification_uri"], browser, incognito)
        
        return {
            "ok": True,
            "user_code": result["user_code"],
            "verification_uri": result["verification_uri"],
            "expires_in": result["expires_in"],
            "interval": result["interval"],
        }
    else:
        return {"ok": False, "error": result.get("error", "未知错误")}


async def poll_kiro_login():
    """轮询 Kiro 登录状态"""
    success, result = await poll_device_flow()
    
    if not success:
        return {"ok": False, "error": result.get("error", "未知错误")}
    
    if result.get("completed"):
        # 授权完成，保存凭证并添加账号
        credentials = result["credentials"]
        
        # 保存到文件
        from ..auth.device_flow import save_credentials_to_file
        file_path = await save_credentials_to_file(credentials)
        
        # 添加账号
        account = Account(
            id=uuid.uuid4().hex[:8],
            name="在线登录账号",
            token_path=file_path
        )
        state.accounts.append(account)
        account.load_credentials()
        state._save_accounts()
        
        return {
            "ok": True,
            "completed": True,
            "account_id": account.id,
            "message": "登录成功，账号已添加"
        }
    else:
        return {
            "ok": True,
            "completed": False,
            "status": result.get("status", "pending")
        }


async def cancel_kiro_login():
    """取消 Kiro 登录"""
    cancelled = cancel_device_flow()
    return {"ok": cancelled}


async def get_kiro_login_status():
    """获取当前登录状态"""
    login_state = get_login_state()
    if login_state:
        return {
            "ok": True,
            "in_progress": True,
            **login_state
        }
    else:
        return {"ok": True, "in_progress": False}


# ==================== Social Auth API (Google/GitHub) ====================

async def start_social_login(request: Request):
    """启动 Social Auth 登录 (Google/GitHub)"""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    provider = body.get("provider", "google")
    browser = body.get("browser", "default")
    incognito = body.get("incognito", False)
    
    success, result = await start_social_auth(provider)
    
    if success:
        # 用指定浏览器打开登录页面
        open_url(result["login_url"], browser, incognito)
        
        return {
            "ok": True,
            "provider": result["provider"],
            "login_url": result["login_url"],
            "state": result["state"],
        }
    else:
        return {"ok": False, "error": result.get("error", "未知错误")}


async def exchange_social_token(request: Request):
    """交换 Social Auth Token"""
    body = await request.json()
    code = body.get("code")
    oauth_state = body.get("state")
    
    if not code or not oauth_state:
        return {"ok": False, "error": "缺少 code 或 state"}
    
    success, result = await exchange_social_auth_token(code, oauth_state)
    
    if not success:
        return {"ok": False, "error": result.get("error", "未知错误")}
    
    if result.get("completed"):
        # 保存凭证并添加账号
        credentials = result["credentials"]
        provider = result.get("provider", "Social")
        
        # 保存到文件
        from ..auth.device_flow import save_credentials_to_file
        file_path = await save_credentials_to_file(credentials, f"kiro-{provider.lower()}-auth")
        
        # 添加账号
        account = Account(
            id=uuid.uuid4().hex[:8],
            name=f"{provider} 登录账号",
            token_path=file_path
        )
        state.accounts.append(account)
        account.load_credentials()
        state._save_accounts()
        
        return {
            "ok": True,
            "completed": True,
            "account_id": account.id,
            "provider": provider,
            "message": f"{provider} 登录成功，账号已添加"
        }
    
    return {"ok": False, "error": "Token 交换失败"}


async def cancel_social_login():
    """取消 Social Auth 登录"""
    cancelled = cancel_social_auth()
    return {"ok": cancelled}


async def get_social_login_status():
    """获取 Social Auth 状态"""
    auth_state = get_social_auth_state()
    if auth_state:
        return {
            "ok": True,
            "in_progress": True,
            **auth_state
        }
    else:
        return {"ok": True, "in_progress": False}


# ==================== Flow Monitor API ====================

async def get_flows(
    protocol: str = None,
    model: str = None,
    account_id: str = None,
    state_filter: str = None,
    has_error: bool = None,
    bookmarked: bool = None,
    search: str = None,
    limit: int = 50,
    offset: int = 0,
):
    """查询 Flows"""
    from ..core.flow_monitor import FlowState
    
    state_enum = None
    if state_filter:
        try:
            state_enum = FlowState(state_filter)
        except ValueError:
            pass
    
    flows = flow_monitor.query(
        protocol=protocol,
        model=model,
        account_id=account_id,
        state=state_enum,
        has_error=has_error,
        bookmarked=bookmarked,
        search=search,
        limit=limit,
        offset=offset,
    )
    
    return {
        "flows": [f.to_dict() for f in flows],
        "total": len(flows),
    }


async def get_flow_detail(flow_id: str):
    """获取 Flow 详情"""
    flow = flow_monitor.get_flow(flow_id)
    if not flow:
        raise HTTPException(404, "Flow not found")
    return flow.to_full_dict()


async def get_flow_stats():
    """获取 Flow 统计"""
    return flow_monitor.get_stats()


async def bookmark_flow(flow_id: str, request: Request):
    """书签 Flow"""
    body = await request.json()
    bookmarked = body.get("bookmarked", True)
    flow_monitor.bookmark_flow(flow_id, bookmarked)
    return {"ok": True}


async def add_flow_note(flow_id: str, request: Request):
    """添加 Flow 备注"""
    body = await request.json()
    note = body.get("note", "")
    flow_monitor.add_note(flow_id, note)
    return {"ok": True}


async def add_flow_tag(flow_id: str, request: Request):
    """添加 Flow 标签"""
    body = await request.json()
    tag = body.get("tag", "")
    if tag:
        flow_monitor.add_tag(flow_id, tag)
    return {"ok": True}


async def export_flows(request: Request):
    """导出 Flows"""
    body = await request.json()
    flow_ids = body.get("flow_ids", [])
    format = body.get("format", "json")
    
    content = flow_monitor.export(flow_ids if flow_ids else None, format)
    return {"content": content, "format": format}


# ==================== Usage API ====================

async def get_account_usage_info(account_id: str):
    """获取账号用量信息"""
    for acc in state.accounts:
        if acc.id == account_id:
            success, result = await get_account_usage(acc)
            if success:
                return {
                    "ok": True,
                    "account_id": account_id,
                    "account_name": acc.name,
                    "usage": {
                        "subscription_title": result.subscription_title,
                        "usage_limit": result.usage_limit,
                        "current_usage": result.current_usage,
                        "balance": result.balance,
                        "is_low_balance": result.is_low_balance,
                        "free_trial_limit": result.free_trial_limit,
                        "free_trial_usage": result.free_trial_usage,
                        "bonus_limit": result.bonus_limit,
                        "bonus_usage": result.bonus_usage,
                    }
                }
            else:
                return {"ok": False, "error": result.get("error", "查询失败")}
    raise HTTPException(404, "Account not found")


# ==================== 账号导入导出 API ====================

async def export_accounts():
    """导出所有账号配置（包含 token）"""
    accounts_data = []
    for acc in state.accounts:
        creds = acc.get_credentials()
        if creds:
            accounts_data.append({
                "name": acc.name,
                "enabled": acc.enabled,
                "credentials": {
                    "accessToken": creds.access_token,
                    "refreshToken": creds.refresh_token,
                    "expiresAt": creds.expires_at,
                    "region": creds.region,
                    "authMethod": creds.auth_method,
                    "clientId": creds.client_id,
                    "clientSecret": creds.client_secret,
                }
            })
    return {
        "ok": True,
        "accounts": accounts_data,
        "exported_at": datetime.now().isoformat(),
        "version": "1.0"
    }


async def import_accounts(request: Request):
    """导入账号配置"""
    body = await request.json()
    accounts_data = body.get("accounts", [])
    imported = 0
    errors = []
    
    for acc_data in accounts_data:
        try:
            creds = acc_data.get("credentials", {})
            if not creds.get("accessToken"):
                errors.append(f"{acc_data.get('name', '未知')}: 缺少 accessToken")
                continue
            
            # 保存凭证到文件
            file_path = await save_credentials_to_file({
                "accessToken": creds.get("accessToken"),
                "refreshToken": creds.get("refreshToken"),
                "expiresAt": creds.get("expiresAt"),
                "region": creds.get("region", "us-east-1"),
                "authMethod": creds.get("authMethod", "social"),
                "clientId": creds.get("clientId"),
                "clientSecret": creds.get("clientSecret"),
            }, f"imported-{uuid.uuid4().hex[:8]}")
            
            # 添加账号
            account = Account(
                id=uuid.uuid4().hex[:8],
                name=acc_data.get("name", "导入账号"),
                token_path=file_path,
                enabled=acc_data.get("enabled", True)
            )
            state.accounts.append(account)
            account.load_credentials()
            imported += 1
        except Exception as e:
            errors.append(f"{acc_data.get('name', '未知')}: {str(e)}")
    
    state._save_accounts()
    return {"ok": True, "imported": imported, "errors": errors}


async def add_manual_token(request: Request):
    """手动添加 Token"""
    body = await request.json()
    access_token = body.get("access_token", "").strip()
    refresh_token = body.get("refresh_token", "").strip()
    name = body.get("name", "手动添加账号")
    
    if not access_token:
        raise HTTPException(400, "缺少 access_token")
    
    # 保存凭证到文件
    file_path = await save_credentials_to_file({
        "accessToken": access_token,
        "refreshToken": refresh_token if refresh_token else None,
        "region": body.get("region", "us-east-1"),
        "authMethod": "social",
    }, f"manual-{uuid.uuid4().hex[:8]}")
    
    # 添加账号
    account = Account(
        id=uuid.uuid4().hex[:8],
        name=name,
        token_path=file_path
    )
    state.accounts.append(account)
    account.load_credentials()
    state._save_accounts()
    
    return {"ok": True, "account_id": account.id}


# ==================== 远程登录链接 API ====================

# 存储远程登录会话
_remote_login_sessions = {}


async def create_remote_login_link(request: Request):
    """创建远程登录链接"""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    
    # 生成唯一 session ID
    session_id = uuid.uuid4().hex
    expires_at = time.time() + 600  # 10 分钟有效期
    
    _remote_login_sessions[session_id] = {
        "status": "pending",
        "created_at": time.time(),
        "expires_at": expires_at,
        "provider": body.get("provider", "google"),
    }
    
    # 获取服务器地址
    host = request.headers.get("host", "localhost:8080")
    scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
    
    login_url = f"{scheme}://{host}/remote-login/{session_id}"
    
    return {
        "ok": True,
        "session_id": session_id,
        "login_url": login_url,
        "expires_in": 600,
    }


async def get_remote_login_status(session_id: str):
    """获取远程登录状态"""
    session = _remote_login_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    if time.time() > session["expires_at"]:
        del _remote_login_sessions[session_id]
        return {"ok": False, "error": "Session expired"}
    
    return {
        "ok": True,
        "status": session["status"],
        "account_id": session.get("account_id"),
    }


async def complete_remote_login(session_id: str, request: Request):
    """完成远程登录（接收 OAuth 回调）"""
    session = _remote_login_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    if time.time() > session["expires_at"]:
        del _remote_login_sessions[session_id]
        raise HTTPException(400, "Session expired")
    
    body = await request.json()
    code = body.get("code")
    oauth_state = body.get("state")
    
    if not code or not oauth_state:
        raise HTTPException(400, "Missing code or state")
    
    # 交换 token
    success, result = await exchange_social_auth_token(code, oauth_state)
    
    if not success:
        session["status"] = "failed"
        session["error"] = result.get("error", "Token exchange failed")
        return {"ok": False, "error": session["error"]}
    
    if result.get("completed"):
        credentials = result["credentials"]
        provider = result.get("provider", "Social")
        
        # 保存凭证
        file_path = await save_credentials_to_file(credentials, f"remote-{provider.lower()}")
        
        # 添加账号
        account = Account(
            id=uuid.uuid4().hex[:8],
            name=f"远程登录 ({provider})",
            token_path=file_path
        )
        state.accounts.append(account)
        account.load_credentials()
        state._save_accounts()
        
        session["status"] = "completed"
        session["account_id"] = account.id
        
        return {
            "ok": True,
            "completed": True,
            "account_id": account.id,
        }
    
    return {"ok": False, "error": "Unexpected state"}


def get_remote_login_page(session_id: str) -> str:
    """生成远程登录页面 HTML"""
    session = _remote_login_sessions.get(session_id)
    if not session or time.time() > session.get("expires_at", 0):
        return """
        <!DOCTYPE html>
        <html><head><title>链接已过期</title></head>
        <body style="font-family:sans-serif;text-align:center;padding:50px">
        <h1>❌ 链接已过期</h1>
        <p>请重新生成登录链接</p>
        </body></html>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kiro Proxy 远程登录</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
            .card {{ background: white; border-radius: 12px; padding: 2rem; max-width: 400px; width: 90%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h1 {{ font-size: 1.5rem; margin-bottom: 1rem; text-align: center; }}
            p {{ color: #666; margin-bottom: 1.5rem; text-align: center; }}
            .btn {{ display: flex; align-items: center; justify-content: center; gap: 0.5rem; width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 8px; background: white; cursor: pointer; font-size: 1rem; margin-bottom: 0.75rem; transition: background 0.2s; }}
            .btn:hover {{ background: #f5f5f5; }}
            .status {{ text-align: center; padding: 1rem; background: #f0f9ff; border-radius: 8px; margin-top: 1rem; display: none; }}
            .input {{ width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 0.75rem; font-size: 1rem; }}
            .submit {{ background: #000; color: white; border: none; }}
            .submit:hover {{ background: #333; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🔐 Kiro Proxy 远程登录</h1>
            <p>选择登录方式完成授权</p>
            
            <button class="btn" onclick="startLogin('google')">
                <svg width="20" height="20" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                Google 登录
            </button>
            
            <button class="btn" onclick="startLogin('github')">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                GitHub 登录
            </button>
            
            <div style="text-align:center;color:#999;margin:1rem 0">或</div>
            
            <p style="font-size:0.875rem;margin-bottom:0.5rem">授权完成后粘贴回调 URL：</p>
            <input type="text" class="input" id="callbackUrl" placeholder="粘贴回调 URL...">
            <button class="btn submit" onclick="submitCallback()">提交</button>
            
            <div class="status" id="status"></div>
        </div>
        
        <script>
            const sessionId = '{session_id}';
            let authState = null;
            
            async function startLogin(provider) {{
                try {{
                    const r = await fetch('/api/kiro/social/start', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{provider}})
                    }});
                    const d = await r.json();
                    if (d.ok) {{
                        authState = d.state;
                        window.open(d.login_url, '_blank');
                        showStatus('请在新窗口完成授权，然后粘贴回调 URL', 'info');
                    }} else {{
                        showStatus('启动登录失败: ' + d.error, 'error');
                    }}
                }} catch(e) {{
                    showStatus('启动登录失败: ' + e.message, 'error');
                }}
            }}
            
            async function submitCallback() {{
                const url = document.getElementById('callbackUrl').value;
                if (!url) {{ showStatus('请粘贴回调 URL', 'error'); return; }}
                
                try {{
                    const urlObj = new URL(url);
                    const code = urlObj.searchParams.get('code');
                    const state = urlObj.searchParams.get('state');
                    if (!code || !state) {{ showStatus('无效的回调 URL', 'error'); return; }}
                    
                    showStatus('正在验证...', 'info');
                    
                    const r = await fetch('/api/remote-login/' + sessionId + '/complete', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{code, state}})
                    }});
                    const d = await r.json();
                    
                    if (d.ok && d.completed) {{
                        showStatus('✅ 登录成功！可以关闭此页面', 'success');
                    }} else {{
                        showStatus('❌ ' + (d.error || '登录失败'), 'error');
                    }}
                }} catch(e) {{
                    showStatus('处理失败: ' + e.message, 'error');
                }}
            }}
            
            function showStatus(msg, type) {{
                const el = document.getElementById('status');
                el.style.display = 'block';
                el.textContent = msg;
                el.style.background = type === 'error' ? '#fef2f2' : type === 'success' ? '#f0fdf4' : '#f0f9ff';
                el.style.color = type === 'error' ? '#dc2626' : type === 'success' ? '#16a34a' : '#0284c7';
            }}
        </script>
    </body>
    </html>
    """


# ==================== 额度管理 API ====================

async def get_accounts_status_enhanced():
    """获取完整账号状态（增强版）"""
    return {
        "ok": True,
        "summary": state.get_accounts_summary(),
        "accounts": state.get_accounts_status()
    }


async def refresh_account_quota(account_id: str):
    """刷新单个账号额度"""
    from ..core import get_quota_scheduler
    scheduler = get_quota_scheduler()
    
    success = await scheduler.refresh_account(account_id)
    
    if success:
        return {"ok": True, "message": f"账号 {account_id} 额度刷新成功"}
    else:
        return {"ok": False, "error": f"账号 {account_id} 额度刷新失败"}


async def refresh_all_quotas():
    """刷新所有账号额度"""
    from ..core import get_quota_scheduler
    scheduler = get_quota_scheduler()
    
    results = await scheduler.refresh_all()
    
    success_count = sum(1 for v in results.values() if v)
    fail_count = len(results) - success_count
    
    return {
        "ok": True,
        "results": results,
        "success_count": success_count,
        "fail_count": fail_count
    }


# ==================== 优先账号 API ====================

async def get_priority_accounts():
    """获取优先账号列表"""
    from ..core import get_account_selector
    selector = get_account_selector()
    
    priority_ids = selector.get_priority_accounts()
    
    # 获取账号详情
    priority_accounts = []
    for pid in priority_ids:
        for acc in state.accounts:
            if acc.id == pid:
                priority_accounts.append({
                    "id": acc.id,
                    "name": acc.name,
                    "enabled": acc.enabled,
                    "available": acc.is_available(),
                    "order": selector.get_priority_order(acc.id)
                })
                break
    
    return {
        "ok": True,
        "priority_accounts": priority_accounts,
        "strategy": selector.strategy.value
    }


async def set_priority_account(account_id: str, request: Request):
    """设置优先账号"""
    from ..core import get_account_selector
    selector = get_account_selector()
    
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    position = body.get("position", -1)
    
    valid_ids = state.get_valid_account_ids()
    success, message = selector.add_priority_account(account_id, position, valid_ids)
    
    return {"ok": success, "message": message}


async def remove_priority_account(account_id: str):
    """取消优先账号"""
    from ..core import get_account_selector
    selector = get_account_selector()
    
    success, message = selector.remove_priority_account(account_id)
    
    return {"ok": success, "message": message}


async def reorder_priority_accounts(request: Request):
    """调整优先账号顺序"""
    from ..core import get_account_selector
    selector = get_account_selector()
    
    body = await request.json()
    account_ids = body.get("account_ids", [])
    
    success, message = selector.reorder_priority(account_ids)
    
    return {"ok": success, "message": message}


# ==================== 汇总统计 API ====================

async def get_accounts_summary():
    """获取账号汇总统计"""
    return {
        "ok": True,
        "summary": state.get_accounts_summary()
    }


# ==================== 刷新进度 API ====================

async def get_refresh_progress():
    """获取刷新进度"""
    from ..core import get_refresh_manager
    manager = get_refresh_manager()
    
    progress = manager.get_progress_dict()
    is_refreshing = manager.is_refreshing()
    
    if progress:
        return {
            "ok": True,
            "is_refreshing": is_refreshing,
            "progress": progress,
            "progress_percent": progress.get("total", 0) and round(
                (progress.get("completed", 0) / progress.get("total", 1)) * 100, 2
            )
        }
    else:
        return {
            "ok": True,
            "is_refreshing": is_refreshing,
            "progress": None,
            "message": "没有进行中的刷新操作"
        }


async def refresh_all_with_progress():
    """批量刷新（带进度和锁检查）
    
    使用 RefreshManager 进行批量刷新，支持：
    - 全局锁防止重复刷新
    - 进度跟踪
    - 自动刷新 Token
    - 重试机制
    
    注意：刷新操作在后台执行，API 立即返回，前端通过轮询获取进度。
    """
    import asyncio
    from ..core import get_refresh_manager, get_account_usage
    manager = get_refresh_manager()
    
    # 检查是否已有刷新在进行
    if manager.is_refreshing():
        progress = manager.get_progress_dict()
        return {
            "ok": False,
            "error": "刷新操作正在进行中",
            "progress": progress
        }
    
    # 定义获取额度的函数
    async def get_quota_func(account):
        """获取账号额度"""
        success, result = await get_account_usage(account)
        if success:
            # 更新额度缓存
            from ..core import get_quota_cache
            from ..core.quota_cache import CachedQuota
            quota_cache = get_quota_cache()
            cached_quota = CachedQuota.from_usage_info(account.id, result)
            quota_cache.set(account.id, cached_quota)
            return True, result
        else:
            return False, result
    
    # 定义后台刷新任务
    async def background_refresh():
        """后台执行刷新"""
        try:
            await manager.refresh_all_with_token(
                accounts=state.accounts,
                get_quota_func=get_quota_func,
                skip_disabled=True,
                skip_error=True
            )
        except Exception as e:
            print(f"[RefreshManager] 后台刷新异常: {e}")
    
    # 启动后台任务，不等待完成
    asyncio.create_task(background_refresh())
    
    # 立即返回，前端通过轮询获取进度
    return {
        "ok": True,
        "message": "刷新任务已启动，请通过 /api/refresh/progress 获取进度"
    }


async def get_refresh_config():
    """获取刷新配置"""
    from ..core import get_refresh_manager
    manager = get_refresh_manager()
    
    config = manager.config
    return {
        "ok": True,
        "config": config.to_dict()
    }


async def update_refresh_config(request: Request):
    """更新刷新配置"""
    from ..core import get_refresh_manager
    manager = get_refresh_manager()
    
    body = await request.json()
    
    try:
        # 更新配置
        manager.update_config(**body)
        
        return {
            "ok": True,
            "config": manager.config.to_dict(),
            "message": "配置更新成功"
        }
    except ValueError as e:
        return {
            "ok": False,
            "error": str(e)
        }


async def get_refresh_manager_status():
    """获取刷新管理器状态"""
    from ..core import get_refresh_manager
    manager = get_refresh_manager()
    
    status = manager.get_status()
    auto_refresh_status = manager.get_auto_refresh_status()
    
    return {
        "ok": True,
        "status": status,
        "auto_refresh": auto_refresh_status,
        "last_refresh_time": manager.get_last_refresh_time()
    }


# ==================== 集成 RefreshManager 到现有刷新接口 ====================

async def refresh_account_token_with_manager(account_id: str):
    """刷新指定账号的 token（集成 RefreshManager）
    
    刷新前自动检查 Token 状态，使用 RefreshManager 的重试机制。
    """
    from ..core import get_refresh_manager
    manager = get_refresh_manager()
    
    # 查找账号
    account = None
    for acc in state.accounts:
        if acc.id == account_id:
            account = acc
            break
    
    if not account:
        return {"ok": False, "error": "账号不存在"}
    
    # 使用 RefreshManager 的重试机制刷新 Token
    success, result = await manager.retry_with_backoff(
        account.refresh_token
    )
    
    if success:
        return {"ok": True, "message": "Token 刷新成功"}
    else:
        return {"ok": False, "error": f"Token 刷新失败: {result}"}


async def refresh_account_quota_with_token(account_id: str):
    """刷新单个账号额度（先刷新 Token）
    
    在获取额度前自动检查并刷新 Token（如果需要）。
    """
    from ..core import get_refresh_manager, get_account_usage, get_quota_cache
    manager = get_refresh_manager()
    
    # 查找账号
    account = None
    for acc in state.accounts:
        if acc.id == account_id:
            account = acc
            break
    
    if not account:
        return {"ok": False, "error": "账号不存在"}
    
    # 先刷新 Token（如果需要）
    token_success, token_msg = await manager.refresh_token_if_needed(account)
    
    if not token_success:
        return {"ok": False, "error": f"Token 刷新失败: {token_msg}"}
    
    # 获取额度
    success, result = await get_account_usage(account)
    
    if success:
        # 更新额度缓存
        from ..core.quota_cache import CachedQuota
        quota_cache = get_quota_cache()
        cached_quota = CachedQuota.from_usage_info(account.id, result)
        quota_cache.set(account.id, cached_quota)
        
        return {
            "ok": True,
            "message": f"账号 {account_id} 额度刷新成功",
            "token_refreshed": token_msg != "Token 有效，无需刷新",
            "usage": {
                "balance": result.balance,
                "current_usage": result.current_usage,
                "usage_limit": result.usage_limit
            }
        }
    else:
        error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
        return {"ok": False, "error": f"获取额度失败: {error_msg}"}
