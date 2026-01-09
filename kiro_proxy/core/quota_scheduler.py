"""额度更新调度器模块

实现启动时并发获取所有账号额度、定时更新活跃账号额度的功能。
"""
import asyncio
import time
from typing import Optional, Set, Dict, List, TYPE_CHECKING
from threading import Lock

if TYPE_CHECKING:
    from .account import Account

from .quota_cache import QuotaCache, CachedQuota, get_quota_cache
from .usage import get_account_usage


# 默认更新间隔（秒）
DEFAULT_UPDATE_INTERVAL = 60

# 活跃账号判定时间窗口（秒）
ACTIVE_WINDOW_SECONDS = 60


class QuotaScheduler:
    """额度更新调度器
    
    负责启动时并发获取所有账号额度，以及定时更新活跃账号的额度。
    """
    
    def __init__(self, 
                 quota_cache: Optional[QuotaCache] = None,
                 update_interval: int = DEFAULT_UPDATE_INTERVAL):
        """
        初始化调度器
        
        Args:
            quota_cache: 额度缓存实例
            update_interval: 更新间隔（秒）
        """
        self.quota_cache = quota_cache or get_quota_cache()
        self.update_interval = update_interval
        
        self._active_accounts: Dict[str, float] = {}  # account_id -> last_used_timestamp
        self._lock = Lock()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_full_refresh: Optional[float] = None
        self._accounts_getter = None  # 获取账号列表的回调函数
    
    def set_accounts_getter(self, getter):
        """设置获取账号列表的回调函数
        
        Args:
            getter: 返回账号列表的可调用对象
        """
        self._accounts_getter = getter
    
    def _get_accounts(self) -> List['Account']:
        """获取账号列表"""
        if self._accounts_getter:
            return self._accounts_getter()
        return []
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        print("[QuotaScheduler] 启动额度更新调度器")
        
        # 启动时刷新所有账号额度
        await self.refresh_all()
        
        # 启动定时更新任务
        self._task = asyncio.create_task(self._update_loop())
    
    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        print("[QuotaScheduler] 额度更新调度器已停止")
    
    async def refresh_all(self) -> Dict[str, bool]:
        """刷新所有账号额度
        
        Returns:
            账号ID -> 是否成功的字典
        """
        accounts = self._get_accounts()
        if not accounts:
            print("[QuotaScheduler] 没有账号需要刷新")
            return {}
        
        # 刷新所有账号（包括禁用的，以便检查是否可以解禁）
        print(f"[QuotaScheduler] 开始刷新 {len(accounts)} 个账号的额度...")
        
        # 并发获取所有账号额度
        tasks = [self._refresh_account_internal(acc) for acc in accounts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = 0
        fail_count = 0
        result_dict = {}
        
        for acc, result in zip(accounts, results):
            if isinstance(result, Exception):
                result_dict[acc.id] = False
                fail_count += 1
            else:
                result_dict[acc.id] = result
                if result:
                    success_count += 1
                else:
                    fail_count += 1
        
        self._last_full_refresh = time.time()
        
        # 保存缓存
        await self.quota_cache.save_to_file_async()
        
        # 保存账号配置（因为可能有启用/禁用状态变化）
        self._save_accounts_config()
        
        print(f"[QuotaScheduler] 额度刷新完成: 成功 {success_count}, 失败 {fail_count}")
        return result_dict
    
    def _save_accounts_config(self):
        """保存账号配置"""
        try:
            from .state import state
            state._save_accounts()
        except Exception as e:
            print(f"[QuotaScheduler] 保存账号配置失败: {e}")
    
    async def refresh_account(self, account_id: str) -> bool:
        """刷新单个账号额度
        
        Args:
            account_id: 账号ID
            
        Returns:
            是否成功
        """
        accounts = self._get_accounts()
        account = next((acc for acc in accounts if acc.id == account_id), None)
        
        if not account:
            print(f"[QuotaScheduler] 账号不存在: {account_id}")
            return False
        
        success = await self._refresh_account_internal(account)
        
        if success:
            await self.quota_cache.save_to_file_async()
            self._save_accounts_config()
        
        return success
    
    async def _refresh_account_internal(self, account: 'Account') -> bool:
        """内部刷新账号额度方法
        
        Args:
            account: 账号对象
            
        Returns:
            是否成功
        """
        try:
            success, result = await get_account_usage(account)
            
            if success:
                quota = CachedQuota.from_usage_info(account.id, result)
                self.quota_cache.set(account.id, quota)
                
                # 额度为 0 时自动禁用账号
                if quota.is_exhausted:
                    if account.enabled:
                        account.enabled = False
                        print(f"[QuotaScheduler] 账号 {account.id} ({account.name}) 额度已用尽，自动禁用")
                else:
                    # 有额度时自动解禁账号
                    if not account.enabled:
                        account.enabled = True
                        print(f"[QuotaScheduler] 账号 {account.id} ({account.name}) 有可用额度，自动启用")
                
                return True
            else:
                error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
                quota = CachedQuota.from_error(account.id, error_msg)
                self.quota_cache.set(account.id, quota)
                print(f"[QuotaScheduler] 获取账号 {account.id} 额度失败: {error_msg}")
                return False
                
        except Exception as e:
            error_msg = str(e)
            quota = CachedQuota.from_error(account.id, error_msg)
            self.quota_cache.set(account.id, quota)
            print(f"[QuotaScheduler] 获取账号 {account.id} 额度异常: {error_msg}")
            return False
    
    def mark_active(self, account_id: str) -> None:
        """标记账号为活跃
        
        Args:
            account_id: 账号ID
        """
        with self._lock:
            self._active_accounts[account_id] = time.time()
    
    def is_active(self, account_id: str) -> bool:
        """检查账号是否活跃
        
        Args:
            account_id: 账号ID
            
        Returns:
            是否在活跃时间窗口内
        """
        with self._lock:
            last_used = self._active_accounts.get(account_id)
            if last_used is None:
                return False
            return (time.time() - last_used) < ACTIVE_WINDOW_SECONDS
    
    def get_active_accounts(self) -> Set[str]:
        """获取活跃账号列表
        
        Returns:
            活跃账号ID集合
        """
        current_time = time.time()
        with self._lock:
            return {
                account_id 
                for account_id, last_used in self._active_accounts.items()
                if (current_time - last_used) < ACTIVE_WINDOW_SECONDS
            }
    
    def cleanup_inactive(self) -> None:
        """清理不活跃的账号记录"""
        current_time = time.time()
        with self._lock:
            self._active_accounts = {
                account_id: last_used
                for account_id, last_used in self._active_accounts.items()
                if (current_time - last_used) < ACTIVE_WINDOW_SECONDS * 2
            }
    
    async def _update_loop(self) -> None:
        """定时更新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.update_interval)
                
                if not self._running:
                    break
                
                # 获取活跃账号
                active_ids = self.get_active_accounts()
                
                if active_ids:
                    print(f"[QuotaScheduler] 更新 {len(active_ids)} 个活跃账号的额度...")
                    
                    accounts = self._get_accounts()
                    active_accounts = [acc for acc in accounts if acc.id in active_ids]
                    
                    # 并发更新
                    tasks = [self._refresh_account_internal(acc) for acc in active_accounts]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # 保存缓存
                    await self.quota_cache.save_to_file_async()
                
                # 清理不活跃记录
                self.cleanup_inactive()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[QuotaScheduler] 更新循环异常: {e}")
    
    def get_last_full_refresh(self) -> Optional[float]:
        """获取最后一次全量刷新时间"""
        return self._last_full_refresh
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "running": self._running,
            "update_interval": self.update_interval,
            "active_accounts": list(self.get_active_accounts()),
            "active_count": len(self.get_active_accounts()),
            "last_full_refresh": self._last_full_refresh
        }


# 全局调度器实例
_quota_scheduler: Optional[QuotaScheduler] = None


def get_quota_scheduler() -> QuotaScheduler:
    """获取全局调度器实例"""
    global _quota_scheduler
    if _quota_scheduler is None:
        _quota_scheduler = QuotaScheduler()
    return _quota_scheduler
