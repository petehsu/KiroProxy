"""额度缓存管理模块

提供账号额度信息的内存缓存和文件持久化功能。
"""
import json
import time
import asyncio
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from threading import Lock


# 默认缓存过期时间（秒）
DEFAULT_CACHE_MAX_AGE = 300  # 5分钟

# 低余额阈值
LOW_BALANCE_THRESHOLD = 0.2


class BalanceStatus(Enum):
    """额度状态枚举
    
    用于区分账号的额度状态：
    - NORMAL: 正常（剩余额度 > 20%）
    - LOW: 低额度（0 < 剩余额度 <= 20%）
    - EXHAUSTED: 无额度（剩余额度 <= 0）
    """
    NORMAL = "normal"       # 正常（>20%）
    LOW = "low"             # 低额度（0-20%）
    EXHAUSTED = "exhausted" # 无额度（<=0）


@dataclass
class CachedQuota:
    """缓存的额度信息"""
    account_id: str
    usage_limit: float = 0.0          # 总额度
    current_usage: float = 0.0        # 已用额度
    balance: float = 0.0              # 剩余额度
    usage_percent: float = 0.0        # 使用百分比
    balance_status: str = "normal"    # 额度状态: normal, low, exhausted
    is_low_balance: bool = False      # 是否低额度（兼容旧字段）
    is_exhausted: bool = False        # 是否无额度
    subscription_title: str = ""      # 订阅类型
    free_trial_limit: float = 0.0     # 免费试用额度
    free_trial_usage: float = 0.0     # 免费试用已用
    bonus_limit: float = 0.0          # 奖励额度
    bonus_usage: float = 0.0          # 奖励已用
    updated_at: float = 0.0           # 更新时间戳
    error: Optional[str] = None       # 错误信息(如果获取失败)
    
    def __post_init__(self):
        """初始化后计算额度状态"""
        self._update_balance_status()
    
    def _update_balance_status(self) -> None:
        """更新额度状态"""
        if self.error is not None:
            # 有错误时不更新状态
            return
        
        if self.balance <= 0:
            self.balance_status = BalanceStatus.EXHAUSTED.value
            self.is_exhausted = True
            self.is_low_balance = False
        elif self.usage_limit > 0:
            remaining_percent = (self.balance / self.usage_limit) * 100
            if remaining_percent <= LOW_BALANCE_THRESHOLD * 100:
                self.balance_status = BalanceStatus.LOW.value
                self.is_low_balance = True
                self.is_exhausted = False
            else:
                self.balance_status = BalanceStatus.NORMAL.value
                self.is_low_balance = False
                self.is_exhausted = False
        else:
            self.balance_status = BalanceStatus.NORMAL.value
            self.is_low_balance = False
            self.is_exhausted = False
    
    @classmethod
    def from_usage_info(cls, account_id: str, usage_info: 'UsageInfo') -> 'CachedQuota':
        """从 UsageInfo 创建 CachedQuota"""
        usage_percent = (usage_info.current_usage / usage_info.usage_limit * 100) if usage_info.usage_limit > 0 else 0.0
        quota = cls(
            account_id=account_id,
            usage_limit=usage_info.usage_limit,
            current_usage=usage_info.current_usage,
            balance=usage_info.balance,
            usage_percent=round(usage_percent, 2),
            is_low_balance=usage_info.is_low_balance,
            subscription_title=usage_info.subscription_title,
            free_trial_limit=usage_info.free_trial_limit,
            free_trial_usage=usage_info.free_trial_usage,
            bonus_limit=usage_info.bonus_limit,
            bonus_usage=usage_info.bonus_usage,
            updated_at=time.time(),
            error=None
        )
        # 重新计算状态以确保一致性
        quota._update_balance_status()
        return quota
    
    @classmethod
    def from_error(cls, account_id: str, error: str) -> 'CachedQuota':
        """创建错误状态的缓存"""
        return cls(
            account_id=account_id,
            updated_at=time.time(),
            error=error
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedQuota':
        """从字典创建"""
        quota = cls(
            account_id=data.get("account_id", ""),
            usage_limit=data.get("usage_limit", 0.0),
            current_usage=data.get("current_usage", 0.0),
            balance=data.get("balance", 0.0),
            usage_percent=data.get("usage_percent", 0.0),
            balance_status=data.get("balance_status", "normal"),
            is_low_balance=data.get("is_low_balance", False),
            is_exhausted=data.get("is_exhausted", False),
            subscription_title=data.get("subscription_title", ""),
            free_trial_limit=data.get("free_trial_limit", 0.0),
            free_trial_usage=data.get("free_trial_usage", 0.0),
            bonus_limit=data.get("bonus_limit", 0.0),
            bonus_usage=data.get("bonus_usage", 0.0),
            updated_at=data.get("updated_at", 0.0),
            error=data.get("error")
        )
        # 重新计算状态以确保一致性
        quota._update_balance_status()
        return quota
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def has_error(self) -> bool:
        """是否有错误"""
        return self.error is not None
    
    def is_available(self) -> bool:
        """额度是否可用（未耗尽且无错误）"""
        return not self.is_exhausted and not self.has_error()
    
    def get_balance_status_enum(self) -> BalanceStatus:
        """获取额度状态枚举"""
        try:
            return BalanceStatus(self.balance_status)
        except ValueError:
            return BalanceStatus.NORMAL


class QuotaCache:
    """额度缓存管理器
    
    提供线程安全的额度缓存操作，支持内存缓存和文件持久化。
    """
    
    def __init__(self, cache_file: Optional[str] = None):
        """
        初始化缓存管理器
        
        Args:
            cache_file: 缓存文件路径，None 则使用默认路径
        """
        self._cache: Dict[str, CachedQuota] = {}
        self._lock = Lock()
        self._save_lock = asyncio.Lock()
        
        # 设置缓存文件路径
        if cache_file:
            self._cache_file = Path(cache_file)
        else:
            from ..config import DATA_DIR
            self._cache_file = DATA_DIR / "quota_cache.json"
        
        # 启动时加载缓存
        self.load_from_file()
    
    def get(self, account_id: str) -> Optional[CachedQuota]:
        """获取账号的缓存额度
        
        Args:
            account_id: 账号ID
            
        Returns:
            缓存的额度信息，不存在则返回 None
        """
        with self._lock:
            return self._cache.get(account_id)
    
    def set(self, account_id: str, quota: CachedQuota) -> None:
        """设置账号的额度缓存
        
        Args:
            account_id: 账号ID
            quota: 额度信息
        """
        with self._lock:
            self._cache[account_id] = quota
    
    def is_stale(self, account_id: str, max_age_seconds: int = DEFAULT_CACHE_MAX_AGE) -> bool:
        """检查缓存是否过期
        
        Args:
            account_id: 账号ID
            max_age_seconds: 最大缓存时间（秒）
            
        Returns:
            True 表示缓存过期或不存在
        """
        with self._lock:
            quota = self._cache.get(account_id)
            if quota is None:
                return True
            return (time.time() - quota.updated_at) > max_age_seconds
    
    def get_all(self) -> Dict[str, CachedQuota]:
        """获取所有缓存
        
        Returns:
            所有账号的额度缓存副本
        """
        with self._lock:
            return dict(self._cache)
    
    def remove(self, account_id: str) -> None:
        """移除账号缓存
        
        Args:
            account_id: 账号ID
        """
        with self._lock:
            self._cache.pop(account_id, None)
    
    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
    
    def load_from_file(self) -> bool:
        """从文件加载缓存
        
        Returns:
            是否加载成功
        """
        if not self._cache_file.exists():
            return False
        
        try:
            with open(self._cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证版本
            version = data.get("version", "1.0")
            accounts_data = data.get("accounts", {})
            
            with self._lock:
                self._cache.clear()
                for account_id, quota_data in accounts_data.items():
                    quota_data["account_id"] = account_id
                    self._cache[account_id] = CachedQuota.from_dict(quota_data)
            
            print(f"[QuotaCache] 从文件加载 {len(self._cache)} 个账号的额度缓存")
            return True
            
        except json.JSONDecodeError as e:
            print(f"[QuotaCache] 缓存文件格式错误: {e}")
            return False
        except Exception as e:
            print(f"[QuotaCache] 加载缓存失败: {e}")
            return False
    
    def save_to_file(self) -> bool:
        """保存缓存到文件（同步版本）
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with self._lock:
                accounts_data = {}
                for account_id, quota in self._cache.items():
                    quota_dict = quota.to_dict()
                    quota_dict.pop("account_id", None)  # 避免重复存储
                    accounts_data[account_id] = quota_dict
            
            data = {
                "version": "1.0",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "accounts": accounts_data
            }
            
            # 写入临时文件后重命名，确保原子性
            temp_file = self._cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.replace(self._cache_file)
            
            return True
            
        except Exception as e:
            print(f"[QuotaCache] 保存缓存失败: {e}")
            return False
    
    async def save_to_file_async(self) -> bool:
        """异步保存缓存到文件
        
        Returns:
            是否保存成功
        """
        async with self._save_lock:
            # 在线程池中执行同步保存
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.save_to_file)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取缓存汇总信息
        
        Returns:
            汇总统计信息
        """
        with self._lock:
            total_balance = 0.0
            total_usage = 0.0
            total_limit = 0.0
            error_count = 0
            stale_count = 0
            
            current_time = time.time()
            
            for quota in self._cache.values():
                if quota.has_error():
                    error_count += 1
                else:
                    total_balance += quota.balance
                    total_usage += quota.current_usage
                    total_limit += quota.usage_limit
                
                if (current_time - quota.updated_at) > DEFAULT_CACHE_MAX_AGE:
                    stale_count += 1
            
            return {
                "total_accounts": len(self._cache),
                "total_balance": round(total_balance, 2),
                "total_usage": round(total_usage, 2),
                "total_limit": round(total_limit, 2),
                "error_count": error_count,
                "stale_count": stale_count
            }


# 全局缓存实例
_quota_cache: Optional[QuotaCache] = None


def get_quota_cache() -> QuotaCache:
    """获取全局缓存实例"""
    global _quota_cache
    if _quota_cache is None:
        _quota_cache = QuotaCache()
    return _quota_cache
