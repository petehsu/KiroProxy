"""全局状态管理"""
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, List, Dict
from pathlib import Path

from ..config import TOKEN_PATH
from ..credential import quota_manager, CredentialStatus
from .account import Account
from .persistence import load_accounts, save_accounts
from .quota_cache import get_quota_cache
from .account_selector import get_account_selector
from .quota_scheduler import get_quota_scheduler


@dataclass
class RequestLog:
    """请求日志"""
    id: str
    timestamp: float
    method: str
    path: str
    model: str
    account_id: Optional[str]
    status: int
    duration_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    error: Optional[str] = None


class ProxyState:
    """全局状态管理"""
    
    def __init__(self):
        self.accounts: List[Account] = []
        self.request_logs: deque = deque(maxlen=1000)
        self.total_requests: int = 0
        self.total_errors: int = 0
        self.session_locks: Dict[str, str] = {}
        self.session_timestamps: Dict[str, float] = {}
        self.start_time: float = time.time()
        self._load_accounts()
    
    def _load_accounts(self):
        """从配置文件加载账号"""
        saved = load_accounts()
        if saved:
            for acc_data in saved:
                # 验证 token 文件存在
                if Path(acc_data.get("token_path", "")).exists():
                    self.accounts.append(Account(
                        id=acc_data["id"],
                        name=acc_data["name"],
                        token_path=acc_data["token_path"],
                        enabled=acc_data.get("enabled", True)
                    ))
            print(f"[State] 从配置加载 {len(self.accounts)} 个账号")
        
        # 如果没有账号，尝试添加默认账号
        if not self.accounts and TOKEN_PATH.exists():
            self.accounts.append(Account(
                id="default",
                name="默认账号",
                token_path=str(TOKEN_PATH)
            ))
            self._save_accounts()
    
    def _save_accounts(self):
        """保存账号到配置文件"""
        accounts_data = [
            {
                "id": acc.id,
                "name": acc.name,
                "token_path": acc.token_path,
                "enabled": acc.enabled
            }
            for acc in self.accounts
        ]
        save_accounts(accounts_data)
    
    def get_available_account(self, session_id: Optional[str] = None) -> Optional[Account]:
        """获取可用账号（支持会话粘性和智能选择）"""
        quota_manager.cleanup_expired()
        
        # 会话粘性
        if session_id and session_id in self.session_locks:
            account_id = self.session_locks[session_id]
            ts = self.session_timestamps.get(session_id, 0)
            if time.time() - ts < 60:
                for acc in self.accounts:
                    if acc.id == account_id and acc.is_available():
                        self.session_timestamps[session_id] = time.time()
                        return acc
        
        # 使用 AccountSelector 选择账号
        selector = get_account_selector()
        account = selector.select(self.accounts, session_id)
        
        if account and session_id:
            self.session_locks[session_id] = account.id
            self.session_timestamps[session_id] = time.time()
        
        return account
    
    def mark_account_used(self, account_id: str) -> None:
        """标记账号被使用"""
        scheduler = get_quota_scheduler()
        scheduler.mark_active(account_id)
        
        for acc in self.accounts:
            if acc.id == account_id:
                acc.last_used = time.time()
                break
    
    def get_next_available_account(self, exclude_id: str) -> Optional[Account]:
        """获取下一个可用账号（排除指定账号）"""
        available = [a for a in self.accounts if a.is_available() and a.id != exclude_id]
        if not available:
            return None
        return min(available, key=lambda a: a.request_count)
    
    def mark_rate_limited(self, account_id: str, duration_seconds: int = 60):
        """标记账号限流"""
        for acc in self.accounts:
            if acc.id == account_id:
                acc.mark_quota_exceeded("Rate limited")
                break
    
    def mark_quota_exceeded(self, account_id: str, reason: str = "Quota exceeded"):
        """标记账号配额超限"""
        for acc in self.accounts:
            if acc.id == account_id:
                acc.mark_quota_exceeded(reason)
                break
    
    async def refresh_account_token(self, account_id: str) -> tuple:
        """刷新指定账号的 token"""
        for acc in self.accounts:
            if acc.id == account_id:
                return await acc.refresh_token()
        return False, "账号不存在"
    
    async def refresh_expiring_tokens(self) -> List[dict]:
        """刷新所有即将过期的 token"""
        results = []
        for acc in self.accounts:
            if acc.enabled and acc.is_token_expiring_soon(10):
                success, msg = await acc.refresh_token()
                results.append({
                    "account_id": acc.id,
                    "success": success,
                    "message": msg
                })
        return results
    
    def add_log(self, log: RequestLog):
        """添加请求日志"""
        self.request_logs.append(log)
        self.total_requests += 1
        if log.error:
            self.total_errors += 1
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        
        # 获取额度汇总
        quota_cache = get_quota_cache()
        quota_summary = quota_cache.get_summary()
        
        # 获取选择器状态
        selector = get_account_selector()
        selector_status = selector.get_status()
        
        # 获取调度器状态
        scheduler = get_quota_scheduler()
        scheduler_status = scheduler.get_status()
        
        return {
            "uptime_seconds": int(uptime),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": f"{(self.total_errors / max(1, self.total_requests) * 100):.1f}%",
            "accounts_total": len(self.accounts),
            "accounts_available": len([a for a in self.accounts if a.is_available()]),
            "accounts_cooldown": len([a for a in self.accounts if a.status == CredentialStatus.COOLDOWN]),
            "recent_logs": len(self.request_logs),
            # 新增字段
            "quota_summary": quota_summary,
            "selector": selector_status,
            "scheduler": scheduler_status,
        }
    
    def get_accounts_status(self) -> List[dict]:
        """获取所有账号状态"""
        return [acc.get_status_info() for acc in self.accounts]

    def get_accounts_summary(self) -> dict:
        """获取账号汇总统计"""
        quota_cache = get_quota_cache()
        selector = get_account_selector()
        scheduler = get_quota_scheduler()
        
        total_balance = 0.0
        total_usage = 0.0
        total_limit = 0.0
        
        available_count = 0
        cooldown_count = 0
        unhealthy_count = 0
        disabled_count = 0
        
        for acc in self.accounts:
            if not acc.enabled:
                disabled_count += 1
            elif acc.status == CredentialStatus.COOLDOWN:
                cooldown_count += 1
            elif acc.status == CredentialStatus.UNHEALTHY:
                unhealthy_count += 1
            elif acc.is_available():
                available_count += 1
            
            quota = quota_cache.get(acc.id)
            if quota and not quota.has_error():
                total_balance += quota.balance
                total_usage += quota.current_usage
                total_limit += quota.usage_limit
        
        last_refresh = scheduler.get_last_full_refresh()
        last_refresh_ago = None
        if last_refresh:
            seconds_ago = time.time() - last_refresh
            if seconds_ago < 60:
                last_refresh_ago = f"{int(seconds_ago)}秒前"
            elif seconds_ago < 3600:
                last_refresh_ago = f"{int(seconds_ago / 60)}分钟前"
            else:
                last_refresh_ago = f"{int(seconds_ago / 3600)}小时前"
        
        return {
            "total_accounts": len(self.accounts),
            "available_accounts": available_count,
            "cooldown_accounts": cooldown_count,
            "unhealthy_accounts": unhealthy_count,
            "disabled_accounts": disabled_count,
            "total_balance": round(total_balance, 2),
            "total_usage": round(total_usage, 2),
            "total_limit": round(total_limit, 2),
            "last_refresh": last_refresh_ago,
            "last_refresh_timestamp": last_refresh,
            "strategy": selector.strategy.value,
            "priority_accounts": selector.get_priority_accounts(),
        }
    
    def get_valid_account_ids(self) -> set:
        """获取所有有效账号ID集合"""
        return {acc.id for acc in self.accounts if acc.enabled}


# 全局状态实例
state = ProxyState()
