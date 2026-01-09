"""账号选择器模块

实现基于剩余额度的智能账号选择策略，支持优先账号配置。
"""
import json
import time
from enum import Enum
from pathlib import Path
from typing import Optional, List, Set, TYPE_CHECKING
from threading import Lock

if TYPE_CHECKING:
    from .account import Account
    from .quota_cache import QuotaCache


class SelectionStrategy(Enum):
    """选择策略"""
    LOWEST_BALANCE = "lowest_balance"    # 剩余额度最少优先
    ROUND_ROBIN = "round_robin"          # 轮询
    LEAST_REQUESTS = "least_requests"    # 请求最少优先


class AccountSelector:
    """账号选择器
    
    根据配置的策略选择最合适的账号，支持优先账号配置。
    """
    
    def __init__(self, quota_cache: 'QuotaCache', priority_file: Optional[str] = None):
        """
        初始化账号选择器
        
        Args:
            quota_cache: 额度缓存实例
            priority_file: 优先账号配置文件路径
        """
        self.quota_cache = quota_cache
        self._priority_accounts: List[str] = []
        self._strategy = SelectionStrategy.LOWEST_BALANCE
        self._lock = Lock()
        self._round_robin_index = 0
        
        # 设置优先账号配置文件路径
        if priority_file:
            self._priority_file = Path(priority_file)
        else:
            from ..config import DATA_DIR
            self._priority_file = DATA_DIR / "priority.json"
        
        # 加载优先账号配置
        self._load_priority_config()
    
    @property
    def strategy(self) -> SelectionStrategy:
        """获取当前选择策略"""
        return self._strategy
    
    @strategy.setter
    def strategy(self, value: SelectionStrategy):
        """设置选择策略"""
        self._strategy = value
        self._save_priority_config()
    
    def select(self, 
               available_accounts: List['Account'],
               session_id: Optional[str] = None) -> Optional['Account']:
        """选择最合适的账号
        
        Args:
            available_accounts: 可用账号列表
            session_id: 会话ID（用于会话粘性，暂未实现）
            
        Returns:
            选中的账号，如果没有可用账号则返回 None
        """
        if not available_accounts:
            return None
        
        with self._lock:
            # 1. 首先检查优先账号
            if self._priority_accounts:
                for priority_id in self._priority_accounts:
                    for account in available_accounts:
                        if account.id == priority_id and account.is_available():
                            return account
            
            # 2. 根据策略选择
            if self._strategy == SelectionStrategy.LOWEST_BALANCE:
                return self._select_lowest_balance(available_accounts)
            elif self._strategy == SelectionStrategy.ROUND_ROBIN:
                return self._select_round_robin(available_accounts)
            elif self._strategy == SelectionStrategy.LEAST_REQUESTS:
                return self._select_least_requests(available_accounts)
            
            # 默认返回第一个可用账号
            return available_accounts[0] if available_accounts else None
    
    def _select_lowest_balance(self, accounts: List['Account']) -> Optional['Account']:
        """选择剩余额度最少的账号"""
        available = [a for a in accounts if a.is_available()]
        if not available:
            return None
        
        def get_balance_and_requests(account: 'Account') -> tuple:
            """获取账号的余额和请求数，用于排序"""
            quota = self.quota_cache.get(account.id)
            balance = quota.balance if quota and not quota.has_error() else float('inf')
            return (balance, account.request_count)
        
        # 按余额升序，余额相同时按请求数升序
        return min(available, key=get_balance_and_requests)
    
    def _select_round_robin(self, accounts: List['Account']) -> Optional['Account']:
        """轮询选择账号"""
        available = [a for a in accounts if a.is_available()]
        if not available:
            return None
        
        self._round_robin_index = self._round_robin_index % len(available)
        account = available[self._round_robin_index]
        self._round_robin_index += 1
        return account
    
    def _select_least_requests(self, accounts: List['Account']) -> Optional['Account']:
        """选择请求数最少的账号"""
        available = [a for a in accounts if a.is_available()]
        if not available:
            return None
        return min(available, key=lambda a: a.request_count)
    
    def set_priority_accounts(self, account_ids: List[str], 
                              valid_account_ids: Optional[Set[str]] = None) -> tuple:
        """设置优先账号列表
        
        Args:
            account_ids: 优先账号ID列表
            valid_account_ids: 有效账号ID集合（用于验证）
            
        Returns:
            (success, message)
        """
        with self._lock:
            # 验证账号是否存在
            if valid_account_ids:
                invalid_ids = [aid for aid in account_ids if aid not in valid_account_ids]
                if invalid_ids:
                    return False, f"账号不存在: {', '.join(invalid_ids)}"
            
            self._priority_accounts = list(account_ids)
            self._save_priority_config()
            return True, f"已设置 {len(account_ids)} 个优先账号"
    
    def add_priority_account(self, account_id: str, 
                             position: int = -1,
                             valid_account_ids: Optional[Set[str]] = None) -> tuple:
        """添加优先账号
        
        Args:
            account_id: 账号ID
            position: 插入位置，-1 表示末尾
            valid_account_ids: 有效账号ID集合（用于验证）
            
        Returns:
            (success, message)
        """
        with self._lock:
            # 验证账号是否存在
            if valid_account_ids and account_id not in valid_account_ids:
                return False, f"账号不存在: {account_id}"
            
            # 检查是否已存在
            if account_id in self._priority_accounts:
                return False, f"账号 {account_id} 已是优先账号"
            
            if position < 0 or position >= len(self._priority_accounts):
                self._priority_accounts.append(account_id)
            else:
                self._priority_accounts.insert(position, account_id)
            
            self._save_priority_config()
            return True, f"已添加优先账号: {account_id}"
    
    def remove_priority_account(self, account_id: str) -> tuple:
        """移除优先账号
        
        Args:
            account_id: 账号ID
            
        Returns:
            (success, message)
        """
        with self._lock:
            if account_id not in self._priority_accounts:
                return False, f"账号 {account_id} 不是优先账号"
            
            self._priority_accounts.remove(account_id)
            self._save_priority_config()
            return True, f"已移除优先账号: {account_id}"
    
    def reorder_priority(self, account_ids: List[str]) -> tuple:
        """重新排序优先账号
        
        Args:
            account_ids: 新的优先账号顺序
            
        Returns:
            (success, message)
        """
        with self._lock:
            # 验证所有账号都在当前优先列表中
            current_set = set(self._priority_accounts)
            new_set = set(account_ids)
            
            if current_set != new_set:
                missing = current_set - new_set
                extra = new_set - current_set
                errors = []
                if missing:
                    errors.append(f"缺少账号: {', '.join(missing)}")
                if extra:
                    errors.append(f"多余账号: {', '.join(extra)}")
                return False, "; ".join(errors)
            
            self._priority_accounts = list(account_ids)
            self._save_priority_config()
            return True, "优先账号顺序已更新"
    
    def get_priority_accounts(self) -> List[str]:
        """获取优先账号列表"""
        with self._lock:
            return list(self._priority_accounts)
    
    def is_priority_account(self, account_id: str) -> bool:
        """检查账号是否为优先账号"""
        with self._lock:
            return account_id in self._priority_accounts
    
    def get_priority_order(self, account_id: str) -> Optional[int]:
        """获取账号的优先级顺序（从1开始）"""
        with self._lock:
            if account_id in self._priority_accounts:
                return self._priority_accounts.index(account_id) + 1
            return None
    
    def _load_priority_config(self) -> bool:
        """从文件加载优先账号配置"""
        if not self._priority_file.exists():
            return False
        
        try:
            with open(self._priority_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._priority_accounts = data.get("priority_accounts", [])
            strategy_str = data.get("strategy", "lowest_balance")
            try:
                self._strategy = SelectionStrategy(strategy_str)
            except ValueError:
                self._strategy = SelectionStrategy.LOWEST_BALANCE
            
            print(f"[AccountSelector] 加载优先账号配置: {len(self._priority_accounts)} 个优先账号")
            return True
            
        except Exception as e:
            print(f"[AccountSelector] 加载优先账号配置失败: {e}")
            return False
    
    def _save_priority_config(self) -> bool:
        """保存优先账号配置到文件"""
        try:
            self._priority_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "version": "1.0",
                "priority_accounts": self._priority_accounts,
                "strategy": self._strategy.value
            }
            
            temp_file = self._priority_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.replace(self._priority_file)
            
            return True
            
        except Exception as e:
            print(f"[AccountSelector] 保存优先账号配置失败: {e}")
            return False
    
    def get_status(self) -> dict:
        """获取选择器状态"""
        with self._lock:
            return {
                "strategy": self._strategy.value,
                "priority_accounts": list(self._priority_accounts),
                "priority_count": len(self._priority_accounts)
            }


# 全局选择器实例
_account_selector: Optional[AccountSelector] = None


def get_account_selector(quota_cache: Optional['QuotaCache'] = None) -> AccountSelector:
    """获取全局选择器实例"""
    global _account_selector
    if _account_selector is None:
        if quota_cache is None:
            from .quota_cache import get_quota_cache
            quota_cache = get_quota_cache()
        _account_selector = AccountSelector(quota_cache)
    return _account_selector
