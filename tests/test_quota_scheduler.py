"""QuotaScheduler 属性测试和单元测试

Property 3: 活跃账号判定
Property 7: 额度耗尽检测
Property 8: 缓存过期检测
Property 9: 获取失败状态标记
"""
import os
import time
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import pytest
from hypothesis import given, strategies as st, settings

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from kiro_proxy.core.quota_cache import QuotaCache, CachedQuota, DEFAULT_CACHE_MAX_AGE
from kiro_proxy.core.quota_scheduler import (
    QuotaScheduler, ACTIVE_WINDOW_SECONDS
)


# ============== Property 3: 活跃账号判定 ==============
# **Validates: Requirements 2.2**

class TestActiveAccountDetermination:
    """Property 3: 活跃账号判定测试"""
    
    @given(
        account_id=st.text(min_size=1, max_size=16, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        seconds_ago=st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_active_account_determination(self, account_id: str, seconds_ago: float):
        """
        Property 3: 活跃账号判定
        *对于任意*账号和任意时间戳，如果账号的最后使用时间在当前时间60秒内，
        则该账号应被判定为活跃账号；否则应被判定为非活跃账号。
        
        **Validates: Requirements 2.2**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            cache = QuotaCache(cache_file=cache_file)
            scheduler = QuotaScheduler(quota_cache=cache)
            
            # 模拟在 seconds_ago 秒前使用账号
            scheduler._active_accounts[account_id] = time.time() - seconds_ago
            
            is_active = scheduler.is_active(account_id)
            
            # 验证活跃判定
            if seconds_ago < ACTIVE_WINDOW_SECONDS:
                assert is_active, f"账号在 {seconds_ago:.1f} 秒前使用，应该是活跃的"
            else:
                assert not is_active, f"账号在 {seconds_ago:.1f} 秒前使用，不应该是活跃的"
    
    def test_mark_active_updates_timestamp(self):
        """标记活跃应该更新时间戳"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            cache = QuotaCache(cache_file=cache_file)
            scheduler = QuotaScheduler(quota_cache=cache)
            
            # 初始不活跃
            assert not scheduler.is_active("test_account")
            
            # 标记活跃
            scheduler.mark_active("test_account")
            
            # 现在应该活跃
            assert scheduler.is_active("test_account")
    
    def test_get_active_accounts(self):
        """获取活跃账号列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            cache = QuotaCache(cache_file=cache_file)
            scheduler = QuotaScheduler(quota_cache=cache)
            
            # 设置一些账号
            scheduler._active_accounts["active_1"] = time.time()
            scheduler._active_accounts["active_2"] = time.time() - 30
            scheduler._active_accounts["inactive"] = time.time() - 120
            
            active = scheduler.get_active_accounts()
            
            assert "active_1" in active
            assert "active_2" in active
            assert "inactive" not in active


# ============== Property 7: 额度耗尽检测 ==============
# **Validates: Requirements 2.4**

class TestQuotaExhaustion:
    """Property 7: 额度耗尽检测测试"""
    
    @given(balance=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_quota_exhaustion_detection(self, balance: float):
        """
        Property 7: 额度耗尽检测
        *对于任意*账号，当其剩余额度为0或负数时，该账号应被标记为不可用状态。
        
        **Validates: Requirements 2.4**
        """
        quota = CachedQuota(
            account_id="test_account",
            usage_limit=1000.0,
            current_usage=1000.0 - balance,
            balance=balance,
            updated_at=time.time()
        )
        
        # is_exhausted 现在是属性而不是方法
        is_exhausted = quota.is_exhausted
        
        if balance <= 0:
            assert is_exhausted, f"余额 {balance} 应该被判定为耗尽"
        else:
            assert not is_exhausted, f"余额 {balance} 不应该被判定为耗尽"
    
    def test_error_quota_not_exhausted(self):
        """有错误的额度不应该被判定为耗尽"""
        quota = CachedQuota(
            account_id="test_account",
            balance=0.0,
            usage_limit=1000.0,
            error="Connection failed"
        )
        
        # 有错误时不更新状态
        assert not quota.is_exhausted


# ============== Property 8: 缓存过期检测 ==============
# **Validates: Requirements 7.3**

class TestCacheStaleDetection:
    """Property 8: 缓存过期检测测试"""
    
    @given(
        age_seconds=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        max_age=st.integers(min_value=60, max_value=600)
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_stale_detection(self, age_seconds: float, max_age: int):
        """
        Property 8: 缓存过期检测
        *对于任意*缓存记录和过期阈值（默认5分钟），如果缓存的更新时间距当前时间超过阈值，
        则该缓存应被判定为过期。
        
        **Validates: Requirements 7.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            cache = QuotaCache(cache_file=cache_file)
            
            quota = CachedQuota(
                account_id="test_account",
                balance=500.0,
                updated_at=time.time() - age_seconds
            )
            cache.set("test_account", quota)
            
            is_stale = cache.is_stale("test_account", max_age_seconds=max_age)
            
            if age_seconds > max_age:
                assert is_stale, f"缓存年龄 {age_seconds:.1f}s 超过阈值 {max_age}s，应该过期"
            else:
                assert not is_stale, f"缓存年龄 {age_seconds:.1f}s 未超过阈值 {max_age}s，不应该过期"
    
    def test_default_max_age(self):
        """默认过期时间为5分钟"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            cache = QuotaCache(cache_file=cache_file)
            
            # 4分钟前的缓存不应该过期
            quota1 = CachedQuota(
                account_id="fresh",
                balance=500.0,
                updated_at=time.time() - 240
            )
            cache.set("fresh", quota1)
            assert not cache.is_stale("fresh")
            
            # 6分钟前的缓存应该过期
            quota2 = CachedQuota(
                account_id="stale",
                balance=500.0,
                updated_at=time.time() - 360
            )
            cache.set("stale", quota2)
            assert cache.is_stale("stale")


# ============== Property 9: 获取失败状态标记 ==============
# **Validates: Requirements 1.3**

class TestFetchFailureMarking:
    """Property 9: 获取失败状态标记测试"""
    
    @given(error_msg=st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_error_marking(self, error_msg: str):
        """
        Property 9: 获取失败状态标记
        *对于任意*账号，当额度获取失败时，该账号的缓存应包含错误信息，
        且账号状态应被标记为额度未知。
        
        **Validates: Requirements 1.3**
        """
        quota = CachedQuota.from_error("test_account", error_msg)
        
        assert quota.has_error(), "应该有错误标记"
        assert quota.error == error_msg, "错误信息应该一致"
        assert quota.account_id == "test_account"
        assert quota.updated_at > 0, "应该有更新时间"
    
    def test_error_quota_fields(self):
        """错误状态的额度字段应该为默认值"""
        quota = CachedQuota.from_error("test_account", "Connection timeout")
        
        assert quota.usage_limit == 0.0
        assert quota.current_usage == 0.0
        assert quota.balance == 0.0
        assert quota.has_error()


# ============== 单元测试：调度器状态 ==============

class TestSchedulerStatus:
    """调度器状态测试"""
    
    def test_initial_status(self):
        """初始状态"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            cache = QuotaCache(cache_file=cache_file)
            scheduler = QuotaScheduler(quota_cache=cache)
            
            status = scheduler.get_status()
            
            assert status["running"] is False
            assert status["update_interval"] == 60
            assert status["active_count"] == 0
            assert status["last_full_refresh"] is None
    
    def test_cleanup_inactive(self):
        """清理不活跃账号"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            cache = QuotaCache(cache_file=cache_file)
            scheduler = QuotaScheduler(quota_cache=cache)
            
            # 添加一些账号
            scheduler._active_accounts["recent"] = time.time()
            scheduler._active_accounts["old"] = time.time() - 200  # 超过 2 * ACTIVE_WINDOW
            
            scheduler.cleanup_inactive()
            
            assert "recent" in scheduler._active_accounts
            assert "old" not in scheduler._active_accounts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
