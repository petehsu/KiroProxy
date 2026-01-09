"""配额管理"""
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class QuotaRecord:
    """配额超限记录"""
    credential_id: str
    exceeded_at: float
    cooldown_until: float
    reason: str


class QuotaManager:
    """配额管理器
    
    管理凭证的配额超限状态：
    - 标记凭证为配额超限
    - 检查凭证是否可用
    - 自动清理过期的冷却状态
    """
    
    QUOTA_KEYWORDS = [
        "rate limit", "quota", "too many requests", "throttl",
        "capacity", "overloaded", "try again later"
    ]
    
    QUOTA_STATUS_CODES = {402, 429, 503, 529}
    
    def __init__(self, cooldown_seconds: int = 300):
        self.cooldown_seconds = cooldown_seconds
        self.exceeded_records: Dict[str, QuotaRecord] = {}
    
    def is_quota_exceeded_error(self, status_code: Optional[int], error_message: str) -> bool:
        """检查是否为配额超限错误"""
        if status_code and status_code in self.QUOTA_STATUS_CODES:
            return True
        
        error_lower = error_message.lower()
        return any(kw in error_lower for kw in self.QUOTA_KEYWORDS)
    
    def mark_exceeded(self, credential_id: str, reason: str, cooldown_seconds: int = None) -> QuotaRecord:
        """标记凭证为配额超限"""
        now = time.time()
        cooldown = cooldown_seconds if cooldown_seconds is not None else self.cooldown_seconds
        record = QuotaRecord(
            credential_id=credential_id,
            exceeded_at=now,
            cooldown_until=now + cooldown,
            reason=reason
        )
        self.exceeded_records[credential_id] = record
        return record
    
    def is_available(self, credential_id: str) -> bool:
        """检查凭证是否可用"""
        record = self.exceeded_records.get(credential_id)
        if not record:
            return True
        
        if time.time() >= record.cooldown_until:
            del self.exceeded_records[credential_id]
            return True
        
        return False
    
    def get_cooldown_remaining(self, credential_id: str) -> Optional[int]:
        """获取剩余冷却时间（秒）"""
        record = self.exceeded_records.get(credential_id)
        if not record:
            return None
        
        remaining = record.cooldown_until - time.time()
        return max(0, int(remaining))
    
    def cleanup_expired(self) -> int:
        """清理过期的冷却记录"""
        now = time.time()
        expired = [k for k, v in self.exceeded_records.items() if now >= v.cooldown_until]
        for k in expired:
            del self.exceeded_records[k]
        return len(expired)
    
    def restore(self, credential_id: str) -> bool:
        """手动恢复凭证"""
        if credential_id in self.exceeded_records:
            del self.exceeded_records[credential_id]
            return True
        return False


# 全局实例
quota_manager = QuotaManager(cooldown_seconds=300)
