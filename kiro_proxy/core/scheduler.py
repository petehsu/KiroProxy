"""后台任务调度器"""
import asyncio
from typing import Optional
from datetime import datetime

from ..http_client import get_httpx_verify_setting, create_async_client


class BackgroundScheduler:
    """后台任务调度器
    
    负责：
    - Token 过期预刷新
    - 账号健康检查
    - 统计数据更新
    """
    
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._refresh_interval = 300  # 5 分钟检查一次
        self._health_check_interval = 600  # 10 分钟健康检查
        self._last_health_check = 0
    
    async def start(self):
        """启动后台任务"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        print("[Scheduler] 后台任务已启动")
    
    async def stop(self):
        """停止后台任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[Scheduler] 后台任务已停止")
    
    async def _run(self):
        """主循环"""
        from . import state
        import time
        
        while self._running:
            try:
                # Token 预刷新
                await self._refresh_expiring_tokens(state)
                
                # 健康检查
                now = time.time()
                if now - self._last_health_check > self._health_check_interval:
                    await self._health_check(state)
                    self._last_health_check = now
                
                await asyncio.sleep(self._refresh_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Scheduler] 错误: {e}")
                await asyncio.sleep(60)
    
    async def _refresh_expiring_tokens(self, state):
        """刷新即将过期的 Token"""
        for acc in state.accounts:
            if not acc.enabled:
                continue
            
            # 提前 15 分钟刷新
            if acc.is_token_expiring_soon(15):
                print(f"[Scheduler] Token 即将过期，预刷新: {acc.name}")
                success, msg = await acc.refresh_token()
                if success:
                    print(f"[Scheduler] Token 刷新成功: {acc.name}")
                else:
                    print(f"[Scheduler] Token 刷新失败: {acc.name} - {msg}")
    
    async def _health_check(self, state):
        """健康检查"""
        import httpx
        from ..config import MODELS_URL
        from ..credential import CredentialStatus
        
        for acc in state.accounts:
            if not acc.enabled:
                continue
            
            try:
                token = acc.get_token()
                if not token:
                    acc.status = CredentialStatus.UNHEALTHY
                    continue
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "content-type": "application/json"
                }
                
                async with create_async_client(timeout=10, account_proxy_url=acc.get_proxy_url()) as client:
                    resp = await client.get(
                        MODELS_URL, 
                        headers=headers,
                        params={"origin": "AI_EDITOR"}
                    )
                    
                    if resp.status_code == 200:
                        if acc.status == CredentialStatus.UNHEALTHY:
                            acc.status = CredentialStatus.ACTIVE
                            print(f"[HealthCheck] 账号恢复健康: {acc.name}")
                    elif resp.status_code == 401:
                        acc.status = CredentialStatus.UNHEALTHY
                        print(f"[HealthCheck] 账号认证失败: {acc.name}")
                    elif resp.status_code == 429:
                        # 配额超限，不改变状态
                        pass
                        
            except Exception as e:
                print(f"[HealthCheck] 检查失败 {acc.name}: {e}")


# 全局调度器实例
scheduler = BackgroundScheduler()
