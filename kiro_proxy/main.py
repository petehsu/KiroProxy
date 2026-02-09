"""Kiro API Proxy - 主应用"""
import json
import uuid
import httpx
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import MODELS_URL
from .core import state, scheduler, stats_manager
from .handlers import anthropic, openai, gemini, admin
from .handlers import responses as responses_handler
from .web import get_html_page
from .credential import generate_machine_id, get_kiro_version


def get_resource_path(relative_path: str) -> Path:
    """获取资源文件路径，支持从打包资源读取"""
    base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(__file__).parent.parent
    return base_path / relative_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    await scheduler.start()
    yield
    # 关闭时
    await scheduler.stop()


app = FastAPI(title="Kiro API Proxy", docs_url="/docs", redoc_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Web UI ====================

@app.get("/", response_class=HTMLResponse)
async def index():
    return get_html_page()


@app.get("/assets/{path:path}")
async def serve_assets(path: str):
    """提供静态资源"""
    file_path = get_resource_path("assets") / path
    if file_path.exists():
        content_type = "image/svg+xml" if path.endswith(".svg") else "application/octet-stream"
        return StreamingResponse(open(file_path, "rb"), media_type=content_type)
    raise HTTPException(status_code=404)


# ==================== API 端点 ====================

@app.get("/v1/models")
async def models():
    """获取可用模型列表"""
    try:
        account = state.get_available_account()
        if not account:
            raise Exception("No available account")
        
        token = account.get_token()
        machine_id = account.get_machine_id()
        kiro_version = get_kiro_version()
        
        headers = {
            "content-type": "application/json",
            "x-amz-user-agent": f"aws-sdk-js/1.0.0 KiroIDE-{kiro_version}-{machine_id}",
            "amz-sdk-invocation-id": str(uuid.uuid4()),
            "Authorization": f"Bearer {token}",
        }
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.get(MODELS_URL, headers=headers, params={"origin": "AI_EDITOR"})
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "object": "list",
                    "data": [
                        {
                            "id": m["modelId"],
                            "object": "model",
                            "owned_by": "kiro",
                            "name": m["modelName"],
                        }
                        for m in data.get("models", [])
                    ]
                }
    except Exception:
        pass
    
    # 降级返回静态列表
    return {"object": "list", "data": [
        {"id": "auto", "object": "model", "owned_by": "kiro", "name": "Auto"},
        {"id": "claude-sonnet-4.5", "object": "model", "owned_by": "kiro", "name": "Claude Sonnet 4.5"},
        {"id": "claude-sonnet-4", "object": "model", "owned_by": "kiro", "name": "Claude Sonnet 4"},
        {"id": "claude-haiku-4.5", "object": "model", "owned_by": "kiro", "name": "Claude Haiku 4.5"},
        {"id": "claude-opus-4.5", "object": "model", "owned_by": "kiro", "name": "Claude Opus 4.5"},
        {"id": "claude-opus-4.6", "object": "model", "owned_by": "kiro", "name": "Claude Opus 4.6"},
    ]}


# Anthropic 协议
@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    return await anthropic.handle_messages(request)

@app.post("/v1/messages/count_tokens")
async def anthropic_count_tokens(request: Request):
    return await anthropic.handle_count_tokens(request)



# OpenAI 协议
@app.post("/v1/chat/completions")
async def openai_chat(request: Request):
    return await openai.handle_chat_completions(request)


# OpenAI Responses API (Codex CLI 新版本)
@app.post("/v1/responses")
async def openai_responses(request: Request):
    return await responses_handler.handle_responses(request)


# Gemini 协议
@app.post("/v1beta/models/{model_name}:generateContent")
@app.post("/v1/models/{model_name}:generateContent")
async def gemini_generate(model_name: str, request: Request):
    return await gemini.handle_generate_content(model_name, request)


# ==================== 管理 API ====================

@app.get("/api/status")
async def api_status():
    return await admin.get_status()

@app.post("/api/event_logging/batch")
async def api_event_logging_batch(request: Request):
    return await admin.event_logging_batch(request)


@app.get("/api/stats")
async def api_stats():
    return await admin.get_stats()


@app.get("/api/logs")
async def api_logs(limit: int = 100):
    return await admin.get_logs(limit)


# ==================== 账号导入导出 API ====================

@app.get("/api/accounts/export")
async def api_export_accounts():
    """导出所有账号配置"""
    return await admin.export_accounts()


@app.post("/api/accounts/import")
async def api_import_accounts(request: Request):
    """导入账号配置"""
    return await admin.import_accounts(request)


@app.post("/api/accounts/manual")
async def api_add_manual_token(request: Request):
    """手动添加 Token"""
    return await admin.add_manual_token(request)


@app.post("/api/accounts/refresh-all")
async def api_refresh_all():
    """刷新所有即将过期的 token"""
    return await admin.refresh_all_tokens()


@app.get("/api/accounts")
async def api_accounts():
    return await admin.get_accounts()


@app.post("/api/accounts")
async def api_add_account(request: Request):
    return await admin.add_account(request)


@app.delete("/api/accounts/{account_id}")
async def api_delete_account(account_id: str):
    return await admin.delete_account(account_id)


@app.post("/api/accounts/{account_id}/toggle")
async def api_toggle_account(account_id: str):
    return await admin.toggle_account(account_id)


@app.post("/api/speedtest")
async def api_speedtest():
    return await admin.speedtest()


@app.get("/api/token/scan")
async def api_scan_tokens():
    return await admin.scan_tokens()


@app.post("/api/token/add-from-scan")
async def api_add_from_scan(request: Request):
    return await admin.add_from_scan(request)


@app.get("/api/config/export")
async def api_export_config():
    return await admin.export_config()


@app.post("/api/config/import")
async def api_import_config(request: Request):
    return await admin.import_config(request)


@app.post("/api/token/refresh-check")
async def api_refresh_check():
    return await admin.refresh_token_check()


@app.post("/api/accounts/{account_id}/refresh")
async def api_refresh_account(account_id: str):
    """刷新指定账号的 token"""
    return await admin.refresh_account_token(account_id)


@app.post("/api/accounts/{account_id}/restore")
async def api_restore_account(account_id: str):
    """恢复账号（从冷却状态）"""
    return await admin.restore_account(account_id)


@app.get("/api/accounts/{account_id}/usage")
async def api_account_usage(account_id: str):
    """获取账号用量信息"""
    return await admin.get_account_usage_info(account_id)


@app.get("/api/accounts/{account_id}")
async def api_account_detail(account_id: str):
    """获取账号详细信息"""
    return await admin.get_account_detail(account_id)


@app.get("/api/quota")
async def api_quota_status():
    """获取配额状态"""
    return await admin.get_quota_status()


@app.get("/api/kiro/login-url")
async def api_login_url():
    return await admin.get_kiro_login_url()


@app.get("/api/stats/detailed")
async def api_detailed_stats():
    """获取详细统计信息"""
    return await admin.get_detailed_stats()


@app.post("/api/health-check")
async def api_health_check():
    """手动触发健康检查"""
    return await admin.run_health_check()


@app.get("/api/browsers")
async def api_browsers():
    """获取可用浏览器列表"""
    return await admin.get_browsers()


# ==================== Kiro 登录 API ====================

@app.post("/api/kiro/login/start")
async def api_kiro_login_start(request: Request):
    """启动 Kiro 设备授权登录"""
    return await admin.start_kiro_login(request)


@app.get("/api/kiro/login/poll")
async def api_kiro_login_poll():
    """轮询登录状态"""
    return await admin.poll_kiro_login()


@app.post("/api/kiro/login/cancel")
async def api_kiro_login_cancel():
    """取消登录"""
    return await admin.cancel_kiro_login()


@app.get("/api/kiro/login/status")
async def api_kiro_login_status():
    """获取登录状态"""
    return await admin.get_kiro_login_status()


# ==================== Social Auth API (Google/GitHub) ====================

@app.post("/api/kiro/social/start")
async def api_social_login_start(request: Request):
    """启动 Social Auth 登录"""
    return await admin.start_social_login(request)


@app.post("/api/kiro/social/exchange")
async def api_social_token_exchange(request: Request):
    """交换 Social Auth Token"""
    return await admin.exchange_social_token(request)


@app.post("/api/kiro/social/cancel")
async def api_social_login_cancel():
    """取消 Social Auth 登录"""
    return await admin.cancel_social_login()


@app.get("/api/kiro/social/status")
async def api_social_login_status():
    """获取 Social Auth 状态"""
    return await admin.get_social_login_status()


# ==================== Flow Monitor API ====================

@app.get("/api/flows")
async def api_flows(
    protocol: str = None,
    model: str = None,
    account_id: str = None,
    state: str = None,
    has_error: bool = None,
    bookmarked: bool = None,
    search: str = None,
    limit: int = 50,
    offset: int = 0,
):
    """查询 Flows"""
    return await admin.get_flows(
        protocol=protocol,
        model=model,
        account_id=account_id,
        state_filter=state,
        has_error=has_error,
        bookmarked=bookmarked,
        search=search,
        limit=limit,
        offset=offset,
    )


@app.get("/api/flows/stats")
async def api_flow_stats():
    """获取 Flow 统计"""
    return await admin.get_flow_stats()


@app.get("/api/flows/{flow_id}")
async def api_flow_detail(flow_id: str):
    """获取 Flow 详情"""
    return await admin.get_flow_detail(flow_id)


@app.post("/api/flows/{flow_id}/bookmark")
async def api_bookmark_flow(flow_id: str, request: Request):
    """书签 Flow"""
    return await admin.bookmark_flow(flow_id, request)


@app.post("/api/flows/{flow_id}/note")
async def api_add_flow_note(flow_id: str, request: Request):
    """添加 Flow 备注"""
    return await admin.add_flow_note(flow_id, request)


@app.post("/api/flows/{flow_id}/tag")
async def api_add_flow_tag(flow_id: str, request: Request):
    """添加 Flow 标签"""
    return await admin.add_flow_tag(flow_id, request)


@app.post("/api/flows/export")
async def api_export_flows(request: Request):
    """导出 Flows"""
    return await admin.export_flows(request)


# ==================== 远程登录 API ====================

@app.post("/api/remote-login/create")
async def api_create_remote_login(request: Request):
    """创建远程登录链接"""
    return await admin.create_remote_login_link(request)


@app.get("/api/remote-login/{session_id}/status")
async def api_remote_login_status(session_id: str):
    """获取远程登录状态"""
    return await admin.get_remote_login_status(session_id)


@app.post("/api/remote-login/{session_id}/complete")
async def api_complete_remote_login(session_id: str, request: Request):
    """完成远程登录"""
    return await admin.complete_remote_login(session_id, request)


@app.get("/remote-login/{session_id}", response_class=HTMLResponse)
async def remote_login_page(session_id: str):
    """远程登录页面"""
    return admin.get_remote_login_page(session_id)


# ==================== 历史消息管理 API ====================

from .core import get_history_config, update_history_config, TruncateStrategy
from .core.rate_limiter import get_rate_limiter

@app.get("/api/settings/history")
async def api_get_history_config():
    """获取历史消息管理配置"""
    config = get_history_config()
    return config.to_dict()


@app.post("/api/settings/history")
async def api_update_history_config(request: Request):
    """更新历史消息管理配置"""
    data = await request.json()
    update_history_config(data)
    return {"ok": True, "config": get_history_config().to_dict()}


# ==================== 限速配置 API ====================

@app.get("/api/settings/rate-limit")
async def api_get_rate_limit_config():
    """获取限速配置"""
    limiter = get_rate_limiter()
    return {
        "enabled": limiter.config.enabled,
        "min_request_interval": limiter.config.min_request_interval,
        "max_requests_per_minute": limiter.config.max_requests_per_minute,
        "global_max_requests_per_minute": limiter.config.global_max_requests_per_minute,
        "quota_cooldown_seconds": limiter.config.quota_cooldown_seconds,
        "stats": limiter.get_stats()
    }


@app.post("/api/settings/rate-limit")
async def api_update_rate_limit_config(request: Request):
    """更新限速配置"""
    data = await request.json()
    limiter = get_rate_limiter()
    limiter.update_config(**data)
    return {"ok": True, "config": {
        "enabled": limiter.config.enabled,
        "min_request_interval": limiter.config.min_request_interval,
        "max_requests_per_minute": limiter.config.max_requests_per_minute,
        "global_max_requests_per_minute": limiter.config.global_max_requests_per_minute,
        "quota_cooldown_seconds": limiter.config.quota_cooldown_seconds,
    }}


# ==================== 文档 API ====================

# 文档标题映射
DOC_TITLES = {
    "zh": {
        "01-quickstart": "快速开始",
        "02-features": "功能特性",
        "03-faq": "常见问题",
        "04-api": "API 参考",
        "05-server-deploy": "服务器部署",
    },
    "en": {
        "01-quickstart": "Quick Start",
        "02-features": "Features",
        "03-faq": "FAQ",
        "04-api": "API Reference",
        "05-server-deploy": "Server Deployment",
    }
}

def _get_docs_dir_for_lang() -> Path:
    """根据当前语言获取文档目录"""
    from .web.i18n import get_current_lang
    lang = get_current_lang()
    lang_docs_dir = get_resource_path(f"kiro_proxy/docs/{lang}")
    if lang_docs_dir.exists():
        return lang_docs_dir, lang
    return get_resource_path("kiro_proxy/docs"), "zh"

@app.get("/api/docs")
async def api_docs_list():
    """获取文档列表"""
    docs_dir, lang = _get_docs_dir_for_lang()
    titles = DOC_TITLES.get(lang, DOC_TITLES["zh"])
    docs = []
    if docs_dir.exists():
        for doc_file in sorted(docs_dir.glob("*.md")):
            doc_id = doc_file.stem
            title = titles.get(doc_id, doc_id)
            docs.append({"id": doc_id, "title": title})
    return {"docs": docs}


@app.get("/api/docs/{doc_id}")
async def api_docs_content(doc_id: str):
    """获取文档内容"""
    docs_dir, lang = _get_docs_dir_for_lang()
    titles = DOC_TITLES.get(lang, DOC_TITLES["zh"])
    doc_file = docs_dir / f"{doc_id}.md"
    if not doc_file.exists():
        # 回退到默认目录
        fallback_dir = get_resource_path("kiro_proxy/docs")
        doc_file = fallback_dir / f"{doc_id}.md"
        if not doc_file.exists():
            error_msg = "Document not found" if lang == "en" else "文档不存在"
            raise HTTPException(status_code=404, detail=error_msg)
    content = doc_file.read_text(encoding="utf-8")
    title = titles.get(doc_id, doc_id)
    return {"id": doc_id, "title": title, "content": content}


# ==================== 启动 ====================

def run(port: int = 8080):
    import uvicorn
    from .core import state
    state.current_port = port  # 设置当前端口供 WebUI 显示
    print(f"\n{'='*50}")
    print(f"  Kiro API Proxy v1.7.16")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run(port)
