"""Kiro API Proxy - 主应用"""
import json
import uuid
import httpx
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import MODELS_URL, MACHINE_ID
from .models import state
from .handlers import anthropic, openai, gemini, admin
from .web.html import HTML_PAGE

app = FastAPI(title="Kiro API Proxy", docs_url="/docs", redoc_url=None)

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
    return HTML_PAGE


@app.get("/assets/{path:path}")
async def serve_assets(path: str):
    """提供静态资源"""
    file_path = Path("assets") / path
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
        headers = {
            "content-type": "application/json",
            "x-amz-user-agent": f"aws-sdk-js/1.0.27 KiroIDE-0.8.0-{MACHINE_ID}",
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


# Gemini 协议
@app.post("/v1beta/models/{model_name}:generateContent")
@app.post("/v1/models/{model_name}:generateContent")
async def gemini_generate(model_name: str, request: Request):
    return await gemini.handle_generate_content(model_name, request)


# ==================== 管理 API ====================

@app.get("/api/status")
async def api_status():
    return await admin.get_status()


@app.get("/api/stats")
async def api_stats():
    return await admin.get_stats()


@app.get("/api/logs")
async def api_logs(limit: int = 100):
    return await admin.get_logs(limit)


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


@app.get("/api/kiro/login-url")
async def api_login_url():
    return await admin.get_kiro_login_url()


# ==================== 启动 ====================

def run(port: int = 8080):
    import uvicorn
    print(f"\n{'='*50}")
    print(f"  Kiro API Proxy v1.1.0")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run(port)
