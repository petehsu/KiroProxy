"""QuotaCache 属性测试和单元测试

Property 1: 缓存存储完整性 - 存储后读取应返回完整数据
Property 2: 缓存持久化往返 - 保存后加载应产生等价状态
"""
import os
import time
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, settings, assume

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from kiro_proxy.core.quota_cache import (
    QuotaCache, CachedQuota, DEFAULT_CACHE_MAX_AGE
)


# ============== 数据生成策略 ==============

# 固定的时间戳范围，避免 hypothesis 的 flaky 问题
FIXED_MAX_TIMESTAMP = 2000000000.0  # 约 2033 年


@st.composite
def valid_quota_strategy(draw):
    """生成有效的 CachedQuota 数据"""
    usage_limit = draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
    current_usage = draw(st.floats(min_value=0.0, max_value=usage_limit, allow_nan=False, allow_infinity=False))
    balance = usage_limit - current_usage
    usage_percent = (current_usage / usage_limit * 100) if usage_limit > 0 else 0.0
    
    free_trial_limit = draw(st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    free_trial_usage = draw(st.floats(min_value=0.0, max_value=free_trial_limit, allow_nan=False, allow_infinity=False))
    
    bonus_limit = draw(st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    bonus_usage = draw(st.floats(min_value=0.0, max_value=bonus_limit, allow_nan=False, allow_infinity=False))
    
    return CachedQuota(
        account_id=draw(st.text(alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'), min_size=1, max_size=32)),
        usage_limit=usage_limit,
        current_usage=current_usage,
        balance=balance,
        usage_percent=round(usage_percent, 2),
        is_low_balance=balance < usage_limit * 0.2 if usage_limit > 0 else False,
        subscription_title=draw(st.text(min_size=0, max_size=50)),
        free_trial_limit=free_trial_limit,
        free_trial_usage=free_trial_usage,
        bonus_limit=bonus_limit,
        bonus_usage=bonus_usage,
        updated_at=draw(st.floats(min_value=0.0, max_value=FIXED_MAX_TIMESTAMP, allow_nan=False, allow_infinity=False)),
        error=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    )


@st.composite
def account_id_strategy(draw):
    """生成有效的账号ID"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
        min_size=1,
        max_size=32
    ))


# ============== Property 1: 缓存存储完整性 ==============
# **Validates: Requirements 1.2, 2.3**

class TestCacheStorageIntegrity:
    """Property 1: 缓存存储完整性测试"""
    
    @given(quota=valid_quota_strategy())
    @settings(max_examples=100)
    def test_set_then_get_returns_complete_data(self, quota: CachedQuota):
        """
        Property 1: 缓存存储完整性
        *对于任意*有效的额度信息，当存储到 QuotaCache 后，
        读取该账号的缓存应返回包含所有必要字段的完整数据。
        
        **Validates: Requirements 1.2, 2.3**
        """
        # 使用临时文件避免影响真实缓存
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            
            # 存储
            cache.set(quota.account_id, quota)
            
            # 读取
            retrieved = cache.get(quota.account_id)
            
            # 验证完整性
            assert retrieved is not None, "缓存应该存在"
            assert retrieved.account_id == quota.account_id, "account_id 应该一致"
            assert retrieved.usage_limit == quota.usage_limit, "usage_limit 应该一致"
            assert retrieved.current_usage == quota.current_usage, "current_usage 应该一致"
            assert retrieved.balance == quota.balance, "balance 应该一致"
            assert retrieved.updated_at == quota.updated_at, "updated_at 应该一致"
            assert retrieved.error == quota.error, "error 应该一致"
            
        finally:
            # 清理临时文件
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(quotas=st.lists(valid_quota_strategy(), min_size=1, max_size=10, unique_by=lambda q: q.account_id))
    @settings(max_examples=50)
    def test_multiple_accounts_stored_independently(self, quotas: list):
        """多个账号的缓存应该独立存储"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            
            # 存储所有账号
            for quota in quotas:
                cache.set(quota.account_id, quota)
            
            # 验证每个账号都能正确读取
            for quota in quotas:
                retrieved = cache.get(quota.account_id)
                assert retrieved is not None
                assert retrieved.account_id == quota.account_id
                assert retrieved.balance == quota.balance
                
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)


# ============== Property 2: 缓存持久化往返 ==============
# **Validates: Requirements 7.1, 7.2**

class TestCachePersistenceRoundTrip:
    """Property 2: 缓存持久化往返测试"""
    
    @given(quotas=st.lists(valid_quota_strategy(), min_size=1, max_size=10, unique_by=lambda q: q.account_id))
    @settings(max_examples=100)
    def test_save_then_load_preserves_data(self, quotas: list):
        """
        Property 2: 缓存持久化往返
        *对于任意*有效的 QuotaCache 状态，保存到文件后再加载，
        应产生等价的缓存状态（所有账号的额度信息保持一致）。
        
        **Validates: Requirements 7.1, 7.2**
        """
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            # 创建并填充缓存
            cache1 = QuotaCache(cache_file=cache_file)
            for quota in quotas:
                cache1.set(quota.account_id, quota)
            
            # 保存到文件
            success = cache1.save_to_file()
            assert success, "保存应该成功"
            
            # 创建新缓存实例并加载
            cache2 = QuotaCache(cache_file=cache_file)
            
            # 验证数据一致性
            all_cache1 = cache1.get_all()
            all_cache2 = cache2.get_all()
            
            assert len(all_cache1) == len(all_cache2), "账号数量应该一致"
            
            for account_id, quota1 in all_cache1.items():
                quota2 = all_cache2.get(account_id)
                assert quota2 is not None, f"账号 {account_id} 应该存在"
                assert quota1.usage_limit == quota2.usage_limit
                assert quota1.current_usage == quota2.current_usage
                assert quota1.balance == quota2.balance
                assert quota1.updated_at == quota2.updated_at
                assert quota1.error == quota2.error
                
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(quota=valid_quota_strategy())
    @settings(max_examples=50)
    def test_dict_roundtrip(self, quota: CachedQuota):
        """CachedQuota 的字典序列化往返"""
        # 转换为字典
        quota_dict = quota.to_dict()
        
        # 从字典恢复
        restored = CachedQuota.from_dict(quota_dict)
        
        # 验证一致性
        assert restored.account_id == quota.account_id
        assert restored.usage_limit == quota.usage_limit
        assert restored.current_usage == quota.current_usage
        assert restored.balance == quota.balance
        assert restored.updated_at == quota.updated_at
        assert restored.error == quota.error


# ============== 单元测试：缓存过期检测 ==============
# **Validates: Requirements 7.3**

class TestCacheExpiration:
    """缓存过期检测单元测试"""
    
    def test_fresh_cache_not_stale(self):
        """新缓存不应该过期"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            quota = CachedQuota(
                account_id="test_account",
                usage_limit=1000.0,
                current_usage=500.0,
                balance=500.0,
                updated_at=time.time()  # 当前时间
            )
            cache.set("test_account", quota)
            
            assert not cache.is_stale("test_account"), "新缓存不应该过期"
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    def test_old_cache_is_stale(self):
        """旧缓存应该过期"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            quota = CachedQuota(
                account_id="test_account",
                usage_limit=1000.0,
                current_usage=500.0,
                balance=500.0,
                updated_at=time.time() - DEFAULT_CACHE_MAX_AGE - 1  # 超过过期时间
            )
            cache.set("test_account", quota)
            
            assert cache.is_stale("test_account"), "旧缓存应该过期"
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    def test_nonexistent_account_is_stale(self):
        """不存在的账号应该被视为过期"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            assert cache.is_stale("nonexistent"), "不存在的账号应该被视为过期"
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)


# ============== 单元测试：文件读写错误处理 ==============
# **Validates: Requirements 7.3**

class TestFileErrorHandling:
    """文件读写错误处理单元测试"""
    
    def test_load_nonexistent_file(self):
        """加载不存在的文件应该返回 False"""
        cache = QuotaCache(cache_file="/nonexistent/path/cache.json")
        result = cache.load_from_file()
        assert result is False
    
    def test_load_invalid_json(self):
        """加载无效 JSON 应该返回 False"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            f.write("invalid json {{{")
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            # 构造函数会尝试加载，但应该处理错误
            assert len(cache.get_all()) == 0
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    def test_remove_account(self):
        """移除账号应该正常工作"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            quota = CachedQuota(
                account_id="test_account",
                usage_limit=1000.0,
                updated_at=time.time()
            )
            cache.set("test_account", quota)
            assert cache.get("test_account") is not None
            
            cache.remove("test_account")
            assert cache.get("test_account") is None
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    def test_clear_cache(self):
        """清空缓存应该正常工作"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            cache = QuotaCache(cache_file=cache_file)
            for i in range(5):
                quota = CachedQuota(
                    account_id=f"account_{i}",
                    usage_limit=1000.0,
                    updated_at=time.time()
                )
                cache.set(f"account_{i}", quota)
            
            assert len(cache.get_all()) == 5
            
            cache.clear()
            assert len(cache.get_all()) == 0
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)


# ============== 单元测试：CachedQuota 辅助方法 ==============

class TestCachedQuotaMethods:
    """CachedQuota 辅助方法测试"""
    
    def test_has_error(self):
        """has_error 方法测试"""
        quota_ok = CachedQuota(account_id="test", error=None)
        quota_err = CachedQuota(account_id="test", error="Some error")
        
        assert not quota_ok.has_error()
        assert quota_err.has_error()
    
    def test_is_exhausted(self):
        """is_exhausted 属性测试"""
        quota_ok = CachedQuota(account_id="test", balance=100.0, usage_limit=1000.0)
        quota_zero = CachedQuota(account_id="test", balance=0.0, usage_limit=1000.0)
        quota_negative = CachedQuota(account_id="test", balance=-10.0, usage_limit=1000.0)
        quota_error = CachedQuota(account_id="test", balance=0.0, usage_limit=1000.0, error="Error")
        
        assert not quota_ok.is_exhausted
        assert quota_zero.is_exhausted
        assert quota_negative.is_exhausted
        assert not quota_error.is_exhausted  # 有错误时不更新状态
    
    def test_balance_status(self):
        """balance_status 属性测试"""
        # 正常状态 (>20%)
        quota_normal = CachedQuota(account_id="test", balance=500.0, usage_limit=1000.0)
        assert quota_normal.balance_status == "normal"
        assert not quota_normal.is_low_balance
        assert not quota_normal.is_exhausted
        
        # 低额度状态 (0-20%)
        quota_low = CachedQuota(account_id="test", balance=100.0, usage_limit=1000.0)
        assert quota_low.balance_status == "low"
        assert quota_low.is_low_balance
        assert not quota_low.is_exhausted
        
        # 无额度状态 (<=0)
        quota_exhausted = CachedQuota(account_id="test", balance=0.0, usage_limit=1000.0)
        assert quota_exhausted.balance_status == "exhausted"
        assert not quota_exhausted.is_low_balance
        assert quota_exhausted.is_exhausted
    
    def test_is_available(self):
        """is_available 方法测试"""
        quota_ok = CachedQuota(account_id="test", balance=100.0, usage_limit=1000.0)
        quota_exhausted = CachedQuota(account_id="test", balance=0.0, usage_limit=1000.0)
        quota_error = CachedQuota(account_id="test", balance=100.0, error="Error")
        
        assert quota_ok.is_available()
        assert not quota_exhausted.is_available()
        assert not quota_error.is_available()
    
    def test_from_error(self):
        """from_error 工厂方法测试"""
        quota = CachedQuota.from_error("test_account", "Connection failed")
        
        assert quota.account_id == "test_account"
        assert quota.error == "Connection failed"
        assert quota.has_error()
        assert quota.updated_at > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============== Property 10: 低额度与无额度区分 ==============
# **Validates: Requirements 5.5, 5.6**

class TestBalanceStatusDistinction:
    """Property 10: 低额度与无额度区分测试"""
    
    @given(
        balance=st.floats(min_value=-100.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        usage_limit=st.floats(min_value=100.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_balance_status_distinction(self, balance: float, usage_limit: float):
        """
        Property 10: 低额度与无额度区分
        *对于任意*账号，当剩余额度大于0但低于总额度的20%时，应标记为"低额度"状态；
        当剩余额度为0或负数时，应标记为"无额度"状态。
        
        **Validates: Requirements 5.5, 5.6**
        """
        quota = CachedQuota(
            account_id="test_account",
            balance=balance,
            usage_limit=usage_limit,
            updated_at=time.time()
        )
        
        remaining_percent = (balance / usage_limit) * 100 if usage_limit > 0 else 0
        
        if balance <= 0:
            # 无额度状态
            assert quota.balance_status == "exhausted", f"余额 {balance} 应该是 exhausted 状态"
            assert quota.is_exhausted, f"余额 {balance} 应该标记为 is_exhausted"
            assert not quota.is_low_balance, f"余额 {balance} 不应该标记为 is_low_balance"
            assert not quota.is_available(), f"余额 {balance} 不应该可用"
        elif remaining_percent <= 20:
            # 低额度状态
            assert quota.balance_status == "low", f"余额 {balance}/{usage_limit} ({remaining_percent:.1f}%) 应该是 low 状态"
            assert quota.is_low_balance, f"余额 {balance}/{usage_limit} 应该标记为 is_low_balance"
            assert not quota.is_exhausted, f"余额 {balance} 不应该标记为 is_exhausted"
            assert quota.is_available(), f"余额 {balance} 应该可用"
        else:
            # 正常状态
            assert quota.balance_status == "normal", f"余额 {balance}/{usage_limit} ({remaining_percent:.1f}%) 应该是 normal 状态"
            assert not quota.is_low_balance, f"余额 {balance}/{usage_limit} 不应该标记为 is_low_balance"
            assert not quota.is_exhausted, f"余额 {balance} 不应该标记为 is_exhausted"
            assert quota.is_available(), f"余额 {balance} 应该可用"
    
    def test_boundary_values(self):
        """边界值测试"""
        # 正好 20%
        quota_20 = CachedQuota(account_id="test", balance=200.0, usage_limit=1000.0)
        assert quota_20.balance_status == "low"
        
        # 刚好超过 20%
        quota_21 = CachedQuota(account_id="test", balance=210.0, usage_limit=1000.0)
        assert quota_21.balance_status == "normal"
        
        # 正好 0
        quota_0 = CachedQuota(account_id="test", balance=0.0, usage_limit=1000.0)
        assert quota_0.balance_status == "exhausted"
        
        # 负数
        quota_neg = CachedQuota(account_id="test", balance=-10.0, usage_limit=1000.0)
        assert quota_neg.balance_status == "exhausted"
