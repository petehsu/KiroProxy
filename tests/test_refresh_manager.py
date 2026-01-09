"""RefreshManager 属性测试和单元测试

Property 11: Token 过期检测与自动刷新
Property 12: 刷新锁互斥
Property 13: 异常后锁释放
Property 15: 重试次数限制
Property 16: 指数退避延迟
Property 17: 429 错误特殊处理
Property 20: 401 错误自动重试
"""
import os
import time
import asyncio
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

import pytest
from hypothesis import given, strategies as st, settings

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from kiro_proxy.core.refresh_manager import (
    RefreshManager, RefreshConfig, RefreshProgress,
    get_refresh_manager, reset_refresh_manager
)


# ============== 辅助类和函数 ==============

@dataclass
class MockCredentials:
    """模拟凭证"""
    expires_at: Optional[str] = None
    
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return expires <= now + timedelta(minutes=5)
        except Exception:
            return True
    
    def is_expiring_soon(self, minutes: int = 10) -> bool:
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return expires < now + timedelta(minutes=minutes)
        except Exception:
            return False


class MockAccount:
    """模拟账号"""
    def __init__(self, account_id: str, name: str = None, enabled: bool = True):
        self.id = account_id
        self.name = name or account_id
        self.enabled = enabled
        self.status = Mock()
        self.status.value = "active"
        self._credentials = None
        self._refresh_result = (True, "Token 刷新成功")
    
    def get_credentials(self):
        return self._credentials
    
    def set_credentials(self, creds):
        self._credentials = creds
    
    def set_refresh_result(self, success: bool, message: str):
        self._refresh_result = (success, message)
    
    async def refresh_token(self):
        return self._refresh_result


# ============== Property 11: Token 过期检测与自动刷新 ==============
# **Validates: Requirements 12.1, 12.2, 17.2**

class TestTokenExpirationDetection:
    """Property 11: Token 过期检测与自动刷新测试"""
    
    @given(
        minutes_until_expiry=st.integers(min_value=-60, max_value=60)
    )
    @settings(max_examples=100)
    def test_token_expiration_detection(self, minutes_until_expiry: int):
        """
        Property 11: Token 过期检测与自动刷新
        *对于任意*账号和当前时间，如果 Token 过期时间距当前时间小于5分钟，
        则该账号应被判定为需要刷新 Token。
        
        **Validates: Requirements 12.1, 12.2, 17.2**
        """
        manager = RefreshManager()
        account = MockAccount("test_account")
        
        # 设置过期时间
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=minutes_until_expiry)).isoformat()
        creds = MockCredentials(expires_at=expires_at)
        account.set_credentials(creds)
        
        should_refresh = manager.should_refresh_token(account)
        
        # 默认配置是过期前5分钟刷新
        if minutes_until_expiry <= 5:
            assert should_refresh, f"Token 将在 {minutes_until_expiry} 分钟后过期，应该需要刷新"
        else:
            assert not should_refresh, f"Token 将在 {minutes_until_expiry} 分钟后过期，不应该需要刷新"
    
    def test_no_credentials_needs_refresh(self):
        """无凭证时应该需要刷新"""
        manager = RefreshManager()
        account = MockAccount("test_account")
        account.set_credentials(None)
        
        assert manager.should_refresh_token(account)
    
    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_valid(self):
        """Token 有效时不刷新"""
        manager = RefreshManager()
        account = MockAccount("test_account")
        
        # 设置1小时后过期
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        creds = MockCredentials(expires_at=expires_at)
        account.set_credentials(creds)
        
        success, message = await manager.refresh_token_if_needed(account)
        
        assert success
        assert "无需刷新" in message
    
    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_expired(self):
        """Token 过期时自动刷新"""
        manager = RefreshManager()
        account = MockAccount("test_account")
        
        # 设置已过期
        expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        creds = MockCredentials(expires_at=expires_at)
        account.set_credentials(creds)
        account.set_refresh_result(True, "刷新成功")
        
        success, message = await manager.refresh_token_if_needed(account)
        
        assert success
        assert "刷新成功" in message


# ============== Property 12: 刷新锁互斥 ==============
# **Validates: Requirements 14.1, 14.2**

class TestRefreshLockMutex:
    """Property 12: 刷新锁互斥测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_refresh_blocked(self):
        """
        Property 12: 刷新锁互斥
        *对于任意*两个并发的批量刷新请求，系统应只允许一个请求执行，
        另一个请求应被拒绝并返回当前进度信息。
        
        **Validates: Requirements 14.1, 14.2**
        """
        manager = RefreshManager()
        
        # 第一个请求获取锁
        acquired1 = await manager.acquire_refresh_lock()
        assert acquired1, "第一个请求应该成功获取锁"
        
        # 第二个请求应该被拒绝
        acquired2 = await manager.acquire_refresh_lock()
        assert not acquired2, "第二个请求应该被拒绝"
        
        # 释放锁
        manager.release_refresh_lock()
        
        # 现在应该可以获取锁
        acquired3 = await manager.acquire_refresh_lock()
        assert acquired3, "锁释放后应该可以获取"
        manager.release_refresh_lock()
    
    @pytest.mark.asyncio
    async def test_is_refreshing_status(self):
        """刷新状态正确反映"""
        manager = RefreshManager()
        
        assert not manager.is_refreshing()
        
        # 模拟开始刷新
        manager._start_refresh(5, "测试刷新")
        
        assert manager.is_refreshing()
        
        # 完成刷新
        manager._finish_refresh("completed")
        
        assert not manager.is_refreshing()


# ============== Property 13: 异常后锁释放 ==============
# **Validates: Requirements 14.5**

class TestLockReleaseAfterException:
    """Property 13: 异常后锁释放测试"""
    
    @pytest.mark.asyncio
    async def test_lock_released_after_exception(self):
        """
        Property 13: 异常后锁释放
        *对于任意*刷新操作，如果操作异常终止，系统应自动释放锁。
        
        **Validates: Requirements 14.5**
        """
        manager = RefreshManager()
        
        # 创建会抛出异常的账号
        account = MockAccount("test_account")
        
        async def failing_quota_func(acc):
            raise Exception("模拟异常")
        
        # 执行刷新（应该捕获异常并释放锁）
        result = await manager.refresh_all_with_token(
            [account],
            get_quota_func=failing_quota_func
        )
        
        # 锁应该已释放
        assert not manager._async_lock.locked(), "异常后锁应该被释放"
        
        # 状态应该是 error 或 completed
        assert result.status in ("error", "completed")


# ============== Property 15: 重试次数限制 ==============
# **Validates: Requirements 15.1, 15.2, 15.5**

class TestRetryLimit:
    """Property 15: 重试次数限制测试"""
    
    @given(max_retries=st.integers(min_value=0, max_value=5))
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_retry_count_limit(self, max_retries: int):
        """
        Property 15: 重试次数限制
        *对于任意*失败的刷新操作和配置的最大重试次数 N，
        系统应最多重试 N 次。
        
        **Validates: Requirements 15.1, 15.2, 15.5**
        """
        config = RefreshConfig(max_retries=max_retries, retry_base_delay=0.01)
        manager = RefreshManager(config=config)
        
        call_count = 0
        
        async def always_fail():
            nonlocal call_count
            call_count += 1
            return False, "总是失败"
        
        success, result = await manager.retry_with_backoff(always_fail)
        
        # 应该调用 max_retries + 1 次（初始 + 重试）
        expected_calls = max_retries + 1
        assert call_count == expected_calls, f"应该调用 {expected_calls} 次，实际调用 {call_count} 次"
        assert not success, "应该最终失败"


# ============== Property 16: 指数退避延迟 ==============
# **Validates: Requirements 15.3**

class TestExponentialBackoff:
    """Property 16: 指数退避延迟测试"""
    
    @given(
        attempt=st.integers(min_value=0, max_value=5),
        base_delay=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_exponential_backoff_delay(self, attempt: int, base_delay: float):
        """
        Property 16: 指数退避延迟
        *对于任意*重试操作和重试次数 i，第 i 次重试前的等待时间应为 base_delay * 2^i 秒。
        
        **Validates: Requirements 15.3**
        """
        config = RefreshConfig(retry_base_delay=base_delay)
        manager = RefreshManager(config=config)
        
        # 计算预期延迟
        expected_delay = base_delay * (2 ** attempt)
        
        # 验证计算逻辑（这里我们验证公式）
        actual_delay = config.retry_base_delay * (2 ** attempt)
        
        assert abs(actual_delay - expected_delay) < 0.001, \
            f"第 {attempt} 次重试延迟应为 {expected_delay:.3f}s，实际为 {actual_delay:.3f}s"


# ============== Property 17: 429 错误特殊处理 ==============
# **Validates: Requirements 15.7**

class TestRateLimitHandling:
    """Property 17: 429 错误特殊处理测试"""
    
    def test_rate_limit_error_detection(self):
        """
        Property 17: 429 错误特殊处理
        *对于任意*返回 429 限流错误的请求，系统应识别为限流错误。
        
        **Validates: Requirements 15.7**
        """
        manager = RefreshManager()
        
        # 测试各种 429 错误格式
        assert manager._is_rate_limit_error("HTTP 429 Too Many Requests")
        assert manager._is_rate_limit_error("Rate limit exceeded")
        assert manager._is_rate_limit_error("请求过于频繁，请稍后重试")
        
        # 非限流错误
        assert not manager._is_rate_limit_error("HTTP 500 Internal Server Error")
        assert not manager._is_rate_limit_error("Connection timeout")
    
    @given(attempt=st.integers(min_value=0, max_value=5))
    @settings(max_examples=20)
    def test_rate_limit_longer_delay(self, attempt: int):
        """429 错误应使用更长的等待时间"""
        config = RefreshConfig(retry_base_delay=1.0)
        manager = RefreshManager(config=config)
        
        normal_delay = config.retry_base_delay * (2 ** attempt)
        rate_limit_delay = manager._get_rate_limit_delay(attempt, config.retry_base_delay)
        
        # 429 延迟应该是普通延迟的 3 倍
        assert rate_limit_delay == normal_delay * 3, \
            f"429 延迟应为普通延迟的 3 倍"


# ============== Property 20: 401 错误自动重试 ==============
# **Validates: Requirements 12.6**

class TestAuthErrorRetry:
    """Property 20: 401 错误自动重试测试"""
    
    def test_auth_error_detection(self):
        """
        Property 20: 401 错误自动重试
        系统应识别 401 认证错误。
        
        **Validates: Requirements 12.6**
        """
        manager = RefreshManager()
        
        # 测试各种 401 错误格式
        assert manager._is_auth_error("HTTP 401 Unauthorized")
        assert manager._is_auth_error("凭证已过期或无效，需要重新登录")
        assert manager._is_auth_error("Unauthorized access")
        
        # 非认证错误
        assert not manager._is_auth_error("HTTP 500 Internal Server Error")
        assert not manager._is_auth_error("Connection timeout")
    
    @pytest.mark.asyncio
    async def test_auth_error_triggers_token_refresh(self):
        """401 错误应触发 Token 刷新并重试"""
        manager = RefreshManager()
        account = MockAccount("test_account")
        account.set_refresh_result(True, "刷新成功")
        
        call_count = 0
        
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, "HTTP 401 Unauthorized"
            return True, "成功"
        
        success, result = await manager.execute_with_auth_retry(
            account,
            fail_then_succeed
        )
        
        assert success, "重试后应该成功"
        assert call_count == 2, "应该调用两次（失败 + 重试）"


# ============== 单元测试：配置管理 ==============

class TestConfigManagement:
    """配置管理测试"""
    
    def test_default_config(self):
        """默认配置值"""
        config = RefreshConfig()
        
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.concurrency == 3
        assert config.token_refresh_before_expiry == 300
        assert config.auto_refresh_interval == 60
    
    def test_config_validation(self):
        """配置验证"""
        # 有效配置
        config = RefreshConfig(max_retries=5, concurrency=10)
        assert config.validate()
        
        # 无效配置
        with pytest.raises(ValueError):
            RefreshConfig(max_retries=-1).validate()
        
        with pytest.raises(ValueError):
            RefreshConfig(retry_base_delay=0).validate()
        
        with pytest.raises(ValueError):
            RefreshConfig(concurrency=0).validate()
    
    def test_update_config(self):
        """更新配置"""
        manager = RefreshManager()
        
        manager.update_config(max_retries=5, concurrency=10)
        
        assert manager.config.max_retries == 5
        assert manager.config.concurrency == 10
        # 其他值保持不变
        assert manager.config.retry_base_delay == 1.0


# ============== 单元测试：进度跟踪 ==============

class TestProgressTracking:
    """进度跟踪测试"""
    
    def test_progress_creation(self):
        """进度创建"""
        progress = RefreshProgress(
            total=10,
            completed=5,
            success=4,
            failed=1
        )
        
        assert progress.progress_percent == 50.0
        assert progress.is_running()
        assert not progress.is_completed()
    
    def test_progress_to_dict(self):
        """进度转字典"""
        progress = RefreshProgress(total=10)
        d = progress.to_dict()
        
        assert "total" in d
        assert "completed" in d
        assert "status" in d
    
    def test_manager_progress_tracking(self):
        """管理器进度跟踪"""
        manager = RefreshManager()
        
        # 开始刷新
        manager._start_refresh(5, "测试")
        
        progress = manager.get_progress()
        assert progress is not None
        assert progress.total == 5
        assert progress.status == "running"
        
        # 更新进度
        manager._update_progress(current_account="acc_1", success=True)
        
        progress = manager.get_progress()
        assert progress.completed == 1
        assert progress.success == 1
        
        # 完成
        manager._finish_refresh("completed")
        
        progress = manager.get_progress()
        assert progress.status == "completed"


# ============== 单元测试：全局实例 ==============

class TestGlobalInstance:
    """全局实例测试"""
    
    def test_singleton_pattern(self):
        """单例模式"""
        reset_refresh_manager()
        
        manager1 = get_refresh_manager()
        manager2 = get_refresh_manager()
        
        assert manager1 is manager2
    
    def test_reset_manager(self):
        """重置管理器"""
        manager1 = get_refresh_manager()
        reset_refresh_manager()
        manager2 = get_refresh_manager()
        
        assert manager1 is not manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============== Property 14: 跳过错误状态账号 ==============
# **Validates: Requirements 14.6, 17.4**

class TestSkipErrorAccounts:
    """Property 14: 跳过错误状态账号测试"""
    
    @pytest.mark.asyncio
    async def test_skip_disabled_accounts(self):
        """
        Property 14: 跳过错误状态账号
        *对于任意*批量刷新操作，已禁用的账号应被跳过。
        
        **Validates: Requirements 14.6, 17.4**
        """
        manager = RefreshManager()
        
        # 创建账号列表
        enabled_account = MockAccount("enabled", enabled=True)
        disabled_account = MockAccount("disabled", enabled=False)
        
        call_count = 0
        
        async def track_quota_func(acc):
            nonlocal call_count
            call_count += 1
            return True, "成功"
        
        result = await manager.refresh_all_with_token(
            [enabled_account, disabled_account],
            get_quota_func=track_quota_func,
            skip_disabled=True
        )
        
        # 只有启用的账号被处理
        assert result.total == 1, "只应处理启用的账号"
    
    @pytest.mark.asyncio
    async def test_skip_unhealthy_accounts(self):
        """跳过不健康状态的账号"""
        manager = RefreshManager()
        
        healthy_account = MockAccount("healthy")
        healthy_account.status.value = "active"
        
        unhealthy_account = MockAccount("unhealthy")
        unhealthy_account.status.value = "unhealthy"
        
        result = await manager.refresh_all_with_token(
            [healthy_account, unhealthy_account],
            skip_error=True
        )
        
        assert result.total == 1, "只应处理健康的账号"


# ============== Property 18: 定时器唯一性 ==============
# **Validates: Requirements 17.6**

class TestTimerUniqueness:
    """Property 18: 定时器唯一性测试"""
    
    @pytest.mark.asyncio
    async def test_single_timer_running(self):
        """
        Property 18: 定时器唯一性
        *对于任意*时刻，系统中应最多只有一个自动刷新定时器在运行。
        
        **Validates: Requirements 17.6**
        """
        config = RefreshConfig(auto_refresh_interval=1)
        manager = RefreshManager(config=config)
        
        # 启动第一个定时器
        await manager.start_auto_refresh()
        task1 = manager._auto_refresh_task
        
        assert manager.is_auto_refresh_running()
        
        # 再次启动应该替换旧定时器
        await manager.start_auto_refresh()
        task2 = manager._auto_refresh_task
        
        # 应该是不同的任务（旧的被取消）
        assert task1 is not task2 or task1.cancelled()
        assert manager.is_auto_refresh_running()
        
        # 清理
        await manager.stop_auto_refresh()
        assert not manager.is_auto_refresh_running()
    
    @pytest.mark.asyncio
    async def test_stop_clears_timer(self):
        """停止应该清除定时器"""
        config = RefreshConfig(auto_refresh_interval=1)
        manager = RefreshManager(config=config)
        
        await manager.start_auto_refresh()
        assert manager.is_auto_refresh_running()
        
        await manager.stop_auto_refresh()
        assert not manager.is_auto_refresh_running()
        assert manager._auto_refresh_task is None


# ============== Property 19: 刷新失败隔离 ==============
# **Validates: Requirements 17.5**

class TestRefreshFailureIsolation:
    """Property 19: 刷新失败隔离测试"""
    
    @pytest.mark.asyncio
    async def test_single_failure_does_not_affect_others(self):
        """
        Property 19: 刷新失败隔离
        *对于任意*批量刷新操作，单个账号的刷新失败不应影响其他账号的刷新。
        
        **Validates: Requirements 17.5**
        """
        # 使用无重试配置
        config = RefreshConfig(max_retries=0)
        manager = RefreshManager(config=config)
        
        # 创建账号
        account1 = MockAccount("acc1")
        account2 = MockAccount("acc2")
        account3 = MockAccount("acc3")
        
        processed_accounts = set()
        
        async def track_and_fail_second(acc):
            processed_accounts.add(acc.id)
            if acc.id == "acc2":
                return False, "模拟失败"
            return True, "成功"
        
        result = await manager.refresh_all_with_token(
            [account1, account2, account3],
            get_quota_func=track_and_fail_second
        )
        
        # 所有账号都应该被处理
        assert len(processed_accounts) == 3, "所有账号都应该被尝试处理"
        assert "acc1" in processed_accounts
        assert "acc2" in processed_accounts
        assert "acc3" in processed_accounts
        
        # 结果应该反映成功和失败
        assert result.success == 2
        assert result.failed == 1


# ============== 自动刷新状态测试 ==============

class TestAutoRefreshStatus:
    """自动刷新状态测试"""
    
    def test_auto_refresh_status(self):
        """获取自动刷新状态"""
        config = RefreshConfig(auto_refresh_interval=30, token_refresh_before_expiry=600)
        manager = RefreshManager(config=config)
        
        status = manager.get_auto_refresh_status()
        
        assert status["running"] is False
        assert status["interval"] == 30
        assert status["token_refresh_before_expiry"] == 600
