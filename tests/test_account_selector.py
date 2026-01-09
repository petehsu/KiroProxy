"""AccountSelector 属性测试和单元测试

Property 4: 最少额度优先选择
Property 5: 优先账号选择
Property 6: 优先账号验证
"""
import os
import time
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Set

import pytest
from hypothesis import given, strategies as st, settings, assume

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from kiro_proxy.core.quota_cache import QuotaCache, CachedQuota
from kiro_proxy.core.account_selector import AccountSelector, SelectionStrategy


# ============== Mock Account 类 ==============

@dataclass
class MockAccount:
    """模拟账号类，用于测试"""
    id: str
    name: str = ""
    enabled: bool = True
    request_count: int = 0
    _available: bool = True
    
    def is_available(self) -> bool:
        return self.enabled and self._available


# ============== 数据生成策略 ==============

@st.composite
def account_id_strategy(draw):
    """生成有效的账号ID"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
        min_size=1,
        max_size=16
    ))


@st.composite
def mock_account_strategy(draw, account_id: Optional[str] = None):
    """生成模拟账号"""
    if account_id is None:
        account_id = draw(account_id_strategy())
    return MockAccount(
        id=account_id,
        name=f"Account {account_id}",
        enabled=draw(st.booleans()),
        request_count=draw(st.integers(min_value=0, max_value=10000)),
        _available=draw(st.booleans())
    )


@st.composite
def accounts_with_quotas_strategy(draw, min_accounts=2, max_accounts=10):
    """生成账号列表和对应的额度缓存"""
    num_accounts = draw(st.integers(min_value=min_accounts, max_value=max_accounts))
    
    accounts = []
    quotas = {}
    
    for i in range(num_accounts):
        account_id = f"acc_{i}"
        account = MockAccount(
            id=account_id,
            name=f"Account {i}",
            enabled=True,
            request_count=draw(st.integers(min_value=0, max_value=1000)),
            _available=True
        )
        accounts.append(account)
        
        # 生成额度信息
        balance = draw(st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
        quotas[account_id] = CachedQuota(
            account_id=account_id,
            usage_limit=1000.0,
            current_usage=1000.0 - balance,
            balance=balance,
            updated_at=time.time()
        )
    
    return accounts, quotas


# ============== Property 4: 最少额度优先选择 ==============
# **Validates: Requirements 3.1, 3.3**

class TestLowestBalanceSelection:
    """Property 4: 最少额度优先选择测试"""
    
    @given(data=st.data())
    @settings(max_examples=100)
    def test_selects_lowest_balance_account(self, data):
        """
        Property 4: 最少额度优先选择
        *对于任意*可用账号列表（无优先账号配置时），选择器应返回剩余额度最少的账号。
        如果存在多个相同最少额度的账号，应返回请求次数最少的账号。
        
        **Validates: Requirements 3.1, 3.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            # 生成账号和额度
            accounts, quotas = data.draw(accounts_with_quotas_strategy(min_accounts=2, max_accounts=5))
            
            # 设置缓存
            for account_id, quota in quotas.items():
                cache.set(account_id, quota)
            
            # 选择账号
            selected = selector.select(accounts)
            
            # 验证选择了余额最少的账号
            assert selected is not None
            
            selected_quota = quotas[selected.id]
            for account in accounts:
                if account.is_available():
                    other_quota = quotas[account.id]
                    # 选中的账号余额应该 <= 其他账号
                    if other_quota.balance < selected_quota.balance:
                        # 如果有更低余额的账号，测试失败
                        assert False, f"应该选择余额更低的账号 {account.id}"
                    elif other_quota.balance == selected_quota.balance:
                        # 余额相同时，请求数应该 <= 其他账号
                        assert selected.request_count <= account.request_count
    
    def test_selects_lowest_balance_simple(self):
        """简单场景：选择余额最少的账号"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            # 创建账号
            accounts = [
                MockAccount(id="acc_1", request_count=10, _available=True, enabled=True),
                MockAccount(id="acc_2", request_count=5, _available=True, enabled=True),
                MockAccount(id="acc_3", request_count=20, _available=True, enabled=True),
            ]
            
            # 设置额度：acc_2 余额最少
            cache.set("acc_1", CachedQuota(account_id="acc_1", balance=500.0, updated_at=time.time()))
            cache.set("acc_2", CachedQuota(account_id="acc_2", balance=100.0, updated_at=time.time()))
            cache.set("acc_3", CachedQuota(account_id="acc_3", balance=800.0, updated_at=time.time()))
            
            selected = selector.select(accounts)
            assert selected is not None
            assert selected.id == "acc_2"
    
    def test_same_balance_selects_least_requests(self):
        """余额相同时选择请求数最少的账号"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            accounts = [
                MockAccount(id="acc_1", request_count=100, _available=True, enabled=True),
                MockAccount(id="acc_2", request_count=50, _available=True, enabled=True),
                MockAccount(id="acc_3", request_count=200, _available=True, enabled=True),
            ]
            
            # 所有账号余额相同
            for acc in accounts:
                cache.set(acc.id, CachedQuota(account_id=acc.id, balance=500.0, updated_at=time.time()))
            
            selected = selector.select(accounts)
            assert selected is not None
            assert selected.id == "acc_2"  # 请求数最少


# ============== Property 5: 优先账号选择 ==============
# **Validates: Requirements 3.2, 4.3, 4.4**

class TestPriorityAccountSelection:
    """Property 5: 优先账号选择测试"""
    
    @given(data=st.data())
    @settings(max_examples=100)
    def test_priority_account_selected_first(self, data):
        """
        Property 5: 优先账号选择
        *对于任意*可用账号列表和优先账号配置，如果优先账号列表中存在可用账号，
        选择器应按优先级顺序返回第一个可用的优先账号；
        如果所有优先账号都不可用，应回退到最少额度优先策略。
        
        **Validates: Requirements 3.2, 4.3, 4.4**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            # 生成账号
            num_accounts = data.draw(st.integers(min_value=3, max_value=6))
            accounts = []
            for i in range(num_accounts):
                account_id = f"acc_{i}"
                accounts.append(MockAccount(
                    id=account_id,
                    enabled=True,
                    _available=True,
                    request_count=data.draw(st.integers(min_value=0, max_value=100))
                ))
                cache.set(account_id, CachedQuota(
                    account_id=account_id,
                    balance=data.draw(st.floats(min_value=100.0, max_value=1000.0, allow_nan=False, allow_infinity=False)),
                    updated_at=time.time()
                ))
            
            # 随机选择一些账号作为优先账号
            priority_count = data.draw(st.integers(min_value=1, max_value=min(3, num_accounts)))
            priority_ids = [accounts[i].id for i in range(priority_count)]
            
            valid_ids = {acc.id for acc in accounts}
            selector.set_priority_accounts(priority_ids, valid_ids)
            
            # 选择账号
            selected = selector.select(accounts)
            
            # 验证选择了第一个可用的优先账号
            assert selected is not None
            
            # 找到第一个可用的优先账号
            first_available_priority = None
            for pid in priority_ids:
                for acc in accounts:
                    if acc.id == pid and acc.is_available():
                        first_available_priority = acc
                        break
                if first_available_priority:
                    break
            
            if first_available_priority:
                assert selected.id == first_available_priority.id
    
    def test_priority_fallback_to_lowest_balance(self):
        """优先账号不可用时回退到最少额度策略"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            accounts = [
                MockAccount(id="acc_1", _available=False, enabled=True),  # 优先但不可用
                MockAccount(id="acc_2", _available=True, enabled=True),
                MockAccount(id="acc_3", _available=True, enabled=True),
            ]
            
            cache.set("acc_1", CachedQuota(account_id="acc_1", balance=1000.0, updated_at=time.time()))
            cache.set("acc_2", CachedQuota(account_id="acc_2", balance=200.0, updated_at=time.time()))
            cache.set("acc_3", CachedQuota(account_id="acc_3", balance=500.0, updated_at=time.time()))
            
            # 设置 acc_1 为优先账号
            selector.set_priority_accounts(["acc_1"], {"acc_1", "acc_2", "acc_3"})
            
            selected = selector.select(accounts)
            
            # 优先账号不可用，应该选择余额最少的 acc_2
            assert selected is not None
            assert selected.id == "acc_2"


# ============== Property 6: 优先账号验证 ==============
# **Validates: Requirements 4.2**

class TestPriorityAccountValidation:
    """Property 6: 优先账号验证测试"""
    
    @given(
        valid_ids=st.lists(account_id_strategy(), min_size=1, max_size=5, unique=True),
        invalid_id=account_id_strategy()
    )
    @settings(max_examples=100)
    def test_invalid_account_rejected(self, valid_ids: list, invalid_id: str):
        """
        Property 6: 优先账号验证
        *对于任意*账号ID，设置为优先账号时，如果该账号不存在或未启用，
        操作应失败并返回错误；如果账号存在且已启用，操作应成功。
        
        **Validates: Requirements 4.2**
        """
        # 确保 invalid_id 不在 valid_ids 中
        assume(invalid_id not in valid_ids)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            valid_set = set(valid_ids)
            
            # 测试添加无效账号
            success, msg = selector.add_priority_account(invalid_id, valid_account_ids=valid_set)
            assert not success, "添加无效账号应该失败"
            
            # 测试添加有效账号
            valid_id = valid_ids[0]
            success, msg = selector.add_priority_account(valid_id, valid_account_ids=valid_set)
            assert success, "添加有效账号应该成功"
    
    def test_set_priority_validates_all_accounts(self):
        """设置优先账号列表时验证所有账号"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            valid_ids = {"acc_1", "acc_2", "acc_3"}
            
            # 包含无效账号的列表应该失败
            success, msg = selector.set_priority_accounts(
                ["acc_1", "invalid_acc"],
                valid_account_ids=valid_ids
            )
            assert not success
            
            # 全部有效的列表应该成功
            success, msg = selector.set_priority_accounts(
                ["acc_1", "acc_2"],
                valid_account_ids=valid_ids
            )
            assert success


# ============== 单元测试：空账号列表和边界情况 ==============
# **Validates: Requirements 3.4**

class TestEdgeCases:
    """边界情况单元测试"""
    
    def test_empty_account_list(self):
        """空账号列表应返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            selected = selector.select([])
            assert selected is None
    
    def test_all_accounts_unavailable(self):
        """所有账号不可用时应返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            accounts = [
                MockAccount(id="acc_1", _available=False, enabled=True),
                MockAccount(id="acc_2", _available=False, enabled=True),
            ]
            
            selected = selector.select(accounts)
            assert selected is None
    
    def test_remove_priority_account(self):
        """移除优先账号"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            selector.set_priority_accounts(["acc_1", "acc_2"], None)
            assert "acc_1" in selector.get_priority_accounts()
            
            success, _ = selector.remove_priority_account("acc_1")
            assert success
            assert "acc_1" not in selector.get_priority_accounts()
            
            # 移除不存在的账号应该失败
            success, _ = selector.remove_priority_account("acc_1")
            assert not success
    
    def test_reorder_priority_accounts(self):
        """重新排序优先账号"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            selector.set_priority_accounts(["acc_1", "acc_2", "acc_3"], None)
            
            # 正确的重排序
            success, _ = selector.reorder_priority(["acc_3", "acc_1", "acc_2"])
            assert success
            assert selector.get_priority_accounts() == ["acc_3", "acc_1", "acc_2"]
            
            # 缺少账号的重排序应该失败
            success, _ = selector.reorder_priority(["acc_3", "acc_1"])
            assert not success
    
    def test_priority_order(self):
        """获取优先级顺序"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "quota_cache.json")
            priority_file = os.path.join(tmpdir, "priority.json")
            
            cache = QuotaCache(cache_file=cache_file)
            selector = AccountSelector(quota_cache=cache, priority_file=priority_file)
            
            selector.set_priority_accounts(["acc_1", "acc_2", "acc_3"], None)
            
            assert selector.get_priority_order("acc_1") == 1
            assert selector.get_priority_order("acc_2") == 2
            assert selector.get_priority_order("acc_3") == 3
            assert selector.get_priority_order("acc_4") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
