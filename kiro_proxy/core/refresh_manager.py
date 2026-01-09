"""Token 刷新管理模块

提供 Token 批量刷新的管理功能，包括：
- 刷新进度跟踪
- 并发控制
- 重试机制配置
- 全局锁防止重复刷新
- Token 过期检测和自动刷新
- 指数退避重试策略
"""
import time
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Tuple, Callable, TYPE_CHECKING
from threading import Lock

if TYPE_CHECKING:
    from .account import Account


@dataclass
class RefreshProgress:
    """刷新进度信息
    
    用于跟踪批量 Token 刷新操作的进度状态。
    
    Attributes:
        total: 需要刷新的账号总数
        completed: 已完成处理的账号数（包括成功和失败）
        success: 刷新成功的账号数
        failed: 刷新失败的账号数
        current_account: 当前正在处理的账号ID
        status: 刷新状态 - running(进行中), completed(已完成), error(出错)
        started_at: 刷新开始时间戳
        message: 状态消息，用于显示当前操作或错误信息
    """
    total: int = 0
    completed: int = 0
    success: int = 0
    failed: int = 0
    current_account: Optional[str] = None
    status: str = "running"  # running, completed, error
    started_at: float = field(default_factory=time.time)
    message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含所有进度信息的字典
        """
        return asdict(self)
    
    @property
    def progress_percent(self) -> float:
        """计算完成百分比
        
        Returns:
            完成百分比（0-100）
        """
        if self.total == 0:
            return 0.0
        return round((self.completed / self.total) * 100, 2)
    
    @property
    def elapsed_seconds(self) -> float:
        """计算已用时间（秒）
        
        Returns:
            从开始到现在的秒数
        """
        return time.time() - self.started_at
    
    def is_running(self) -> bool:
        """检查是否正在运行
        
        Returns:
            True 表示正在运行
        """
        return self.status == "running"
    
    def is_completed(self) -> bool:
        """检查是否已完成
        
        Returns:
            True 表示已完成（成功或出错）
        """
        return self.status in ("completed", "error")


@dataclass
class RefreshConfig:
    """刷新配置
    
    控制 Token 刷新行为的配置参数。
    
    Attributes:
        max_retries: 单个账号刷新失败时的最大重试次数
        retry_base_delay: 重试基础延迟时间（秒），实际延迟会指数增长
        concurrency: 并发刷新的账号数量
        token_refresh_before_expiry: Token 过期前多少秒开始刷新（默认5分钟）
        auto_refresh_interval: 自动刷新检查间隔（秒）
    """
    max_retries: int = 3
    retry_base_delay: float = 1.0
    concurrency: int = 3
    token_refresh_before_expiry: int = 300  # 5分钟
    auto_refresh_interval: int = 60  # 1分钟
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含所有配置项的字典
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RefreshConfig':
        """从字典创建配置实例
        
        Args:
            data: 配置字典
            
        Returns:
            RefreshConfig 实例
        """
        return cls(
            max_retries=data.get("max_retries", 3),
            retry_base_delay=data.get("retry_base_delay", 1.0),
            concurrency=data.get("concurrency", 3),
            token_refresh_before_expiry=data.get("token_refresh_before_expiry", 300),
            auto_refresh_interval=data.get("auto_refresh_interval", 60)
        )
    
    def validate(self) -> bool:
        """验证配置有效性
        
        Returns:
            True 表示配置有效
            
        Raises:
            ValueError: 配置值无效时抛出
        """
        if self.max_retries < 0:
            raise ValueError("max_retries 不能为负数")
        if self.retry_base_delay <= 0:
            raise ValueError("retry_base_delay 必须大于0")
        if self.concurrency < 1:
            raise ValueError("concurrency 必须至少为1")
        if self.token_refresh_before_expiry < 0:
            raise ValueError("token_refresh_before_expiry 不能为负数")
        if self.auto_refresh_interval < 1:
            raise ValueError("auto_refresh_interval 必须至少为1秒")
        return True


class RefreshManager:
    """Token 刷新管理器
    
    管理 Token 批量刷新操作，提供：
    - 全局锁机制防止重复刷新
    - 进度跟踪
    - 配置管理
    - 自动 Token 刷新定时器
    
    使用示例:
        manager = get_refresh_manager()
        if not manager.is_refreshing():
            # 开始刷新操作
            pass
    """
    
    def __init__(self, config: Optional[RefreshConfig] = None):
        """初始化刷新管理器
        
        Args:
            config: 刷新配置，None 则使用默认配置
        """
        # 配置
        self._config = config or RefreshConfig()
        
        # 线程锁（用于同步访问状态）
        self._lock = Lock()
        
        # 异步锁（用于防止并发刷新操作）
        self._async_lock = asyncio.Lock()
        
        # 刷新状态
        self._is_refreshing: bool = False
        self._progress: Optional[RefreshProgress] = None
        
        # 上次刷新完成时间
        self._last_refresh_time: Optional[float] = None
        
        # 自动刷新定时器
        self._auto_refresh_task: Optional[asyncio.Task] = None
        self._auto_refresh_running: bool = False
        
        # 获取账号列表的回调函数
        self._accounts_getter: Optional[Callable] = None
    
    @property
    def config(self) -> RefreshConfig:
        """获取当前配置
        
        Returns:
            当前的刷新配置
        """
        with self._lock:
            return self._config
    
    def is_refreshing(self) -> bool:
        """检查是否正在刷新
        
        Returns:
            True 表示正在进行刷新操作
        """
        with self._lock:
            return self._is_refreshing
    
    def get_progress(self) -> Optional[RefreshProgress]:
        """获取当前刷新进度
        
        Returns:
            当前进度信息，如果没有进行中的刷新则返回 None
        """
        with self._lock:
            return self._progress
    
    def get_progress_dict(self) -> Optional[Dict[str, Any]]:
        """获取当前刷新进度（字典格式）
        
        Returns:
            进度信息字典，如果没有进行中的刷新则返回 None
        """
        with self._lock:
            if self._progress is None:
                return None
            return self._progress.to_dict()
    
    def update_config(self, **kwargs) -> None:
        """更新配置参数
        
        支持的参数:
            max_retries: 最大重试次数
            retry_base_delay: 重试基础延迟
            concurrency: 并发数
            token_refresh_before_expiry: Token 过期前刷新时间
            auto_refresh_interval: 自动刷新检查间隔
        
        Args:
            **kwargs: 要更新的配置项
            
        Raises:
            ValueError: 配置值无效时抛出
        """
        with self._lock:
            # 创建新配置
            new_config = RefreshConfig(
                max_retries=kwargs.get("max_retries", self._config.max_retries),
                retry_base_delay=kwargs.get("retry_base_delay", self._config.retry_base_delay),
                concurrency=kwargs.get("concurrency", self._config.concurrency),
                token_refresh_before_expiry=kwargs.get(
                    "token_refresh_before_expiry", 
                    self._config.token_refresh_before_expiry
                ),
                auto_refresh_interval=kwargs.get(
                    "auto_refresh_interval", 
                    self._config.auto_refresh_interval
                )
            )
            
            # 验证配置
            new_config.validate()
            
            # 应用新配置
            self._config = new_config
    
    def _start_refresh(self, total: int, message: Optional[str] = None) -> RefreshProgress:
        """开始刷新操作（内部方法）
        
        Args:
            total: 需要刷新的账号总数
            message: 初始状态消息
            
        Returns:
            新创建的进度对象
        """
        with self._lock:
            self._is_refreshing = True
            self._progress = RefreshProgress(
                total=total,
                completed=0,
                success=0,
                failed=0,
                current_account=None,
                status="running",
                started_at=time.time(),
                message=message or "开始刷新"
            )
            return self._progress
    
    def _update_progress(
        self,
        current_account: Optional[str] = None,
        success: bool = False,
        failed: bool = False,
        message: Optional[str] = None
    ) -> None:
        """更新刷新进度（内部方法）
        
        Args:
            current_account: 当前处理的账号ID
            success: 是否成功完成一个账号
            failed: 是否失败一个账号
            message: 状态消息
        """
        with self._lock:
            if self._progress is None:
                return
            
            if current_account is not None:
                self._progress.current_account = current_account
            
            if success:
                self._progress.success += 1
                self._progress.completed += 1
            elif failed:
                self._progress.failed += 1
                self._progress.completed += 1
            
            if message is not None:
                self._progress.message = message
    
    def _finish_refresh(self, status: str = "completed", message: Optional[str] = None) -> None:
        """完成刷新操作（内部方法）
        
        Args:
            status: 最终状态 - completed 或 error
            message: 最终状态消息
        """
        with self._lock:
            self._is_refreshing = False
            self._last_refresh_time = time.time()
            
            if self._progress is not None:
                self._progress.status = status
                self._progress.current_account = None
                if message is not None:
                    self._progress.message = message
                elif status == "completed":
                    self._progress.message = (
                        f"刷新完成: 成功 {self._progress.success}, "
                        f"失败 {self._progress.failed}"
                    )
    
    def get_last_refresh_time(self) -> Optional[float]:
        """获取上次刷新完成时间
        
        Returns:
            上次刷新完成的时间戳，如果从未刷新则返回 None
        """
        with self._lock:
            return self._last_refresh_time
    
    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态
        
        Returns:
            包含管理器状态信息的字典
        """
        with self._lock:
            return {
                "is_refreshing": self._is_refreshing,
                "progress": self._progress.to_dict() if self._progress else None,
                "last_refresh_time": self._last_refresh_time,
                "config": self._config.to_dict()
            }
    
    async def acquire_refresh_lock(self) -> bool:
        """尝试获取刷新锁
        
        用于在开始刷新操作前获取异步锁，防止并发刷新。
        
        Returns:
            True 表示成功获取锁，False 表示已有刷新在进行
        """
        if self._async_lock.locked():
            return False
        
        await self._async_lock.acquire()
        return True
    
    def release_refresh_lock(self) -> None:
        """释放刷新锁
        
        在刷新操作完成后调用，释放异步锁。
        """
        if self._async_lock.locked():
            self._async_lock.release()
    
    def should_refresh_token(self, account: 'Account') -> bool:
        """判断是否需要刷新 Token
        
        检查账号的 Token 是否即将过期（过期前5分钟）或已过期。
        
        Args:
            account: 账号对象
            
        Returns:
            True 表示需要刷新 Token
        """
        creds = account.get_credentials()
        if creds is None:
            return True  # 无法获取凭证，需要刷新
        
        # 检查是否已过期或即将过期
        minutes_before = self._config.token_refresh_before_expiry // 60
        return creds.is_expired() or creds.is_expiring_soon(minutes=minutes_before)
    
    async def refresh_token_if_needed(self, account: 'Account') -> Tuple[bool, str]:
        """如果需要则刷新 Token
        
        检查账号 Token 状态，如果即将过期或已过期则刷新。
        
        Args:
            account: 账号对象
            
        Returns:
            (success, message) 元组
            - success: True 表示 Token 有效（无需刷新或刷新成功）
            - message: 状态消息
        """
        if not self.should_refresh_token(account):
            return True, "Token 有效，无需刷新"
        
        print(f"[RefreshManager] 账号 {account.id} Token 即将过期，开始刷新...")
        
        success, result = await account.refresh_token()
        
        if success:
            print(f"[RefreshManager] 账号 {account.id} Token 刷新成功")
            return True, "Token 刷新成功"
        else:
            print(f"[RefreshManager] 账号 {account.id} Token 刷新失败: {result}")
            return False, f"Token 刷新失败: {result}"
    
    async def refresh_account_with_token(
        self, 
        account: 'Account',
        get_quota_func: Optional[Callable] = None
    ) -> Tuple[bool, str]:
        """刷新单个账号（先刷新 Token，再获取额度）
        
        Args:
            account: 账号对象
            get_quota_func: 获取额度的异步函数，接受 account 参数
            
        Returns:
            (success, message) 元组
        """
        # 1. 先刷新 Token（如果需要）
        token_success, token_msg = await self.refresh_token_if_needed(account)
        
        if not token_success:
            return False, token_msg
        
        # 2. 获取额度（如果提供了获取函数）
        if get_quota_func:
            try:
                quota_success, quota_result = await get_quota_func(account)
                if quota_success:
                    return True, "刷新成功"
                else:
                    error_msg = quota_result.get("error", "Unknown error") if isinstance(quota_result, dict) else str(quota_result)
                    return False, f"获取额度失败: {error_msg}"
            except Exception as e:
                return False, f"获取额度异常: {str(e)}"
        
        return True, token_msg
    
    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> Tuple[bool, Any]:
        """带指数退避的重试
        
        执行异步函数，失败时使用指数退避策略重试。
        
        Args:
            func: 要执行的异步函数
            *args: 传递给函数的位置参数
            max_retries: 最大重试次数，None 则使用配置值
            **kwargs: 传递给函数的关键字参数
            
        Returns:
            (success, result) 元组
            - success: True 表示执行成功
            - result: 成功时为函数返回值，失败时为错误信息
        """
        retries = max_retries if max_retries is not None else self._config.max_retries
        base_delay = self._config.retry_base_delay
        
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                # 检查返回值格式
                if isinstance(result, tuple) and len(result) == 2:
                    success, data = result
                    if success:
                        return True, data
                    else:
                        last_error = data
                        # 检查是否是 429 错误
                        if self._is_rate_limit_error(data):
                            delay = self._get_rate_limit_delay(attempt, base_delay)
                        else:
                            delay = base_delay * (2 ** attempt)
                else:
                    # 函数返回非元组，视为成功
                    return True, result
                    
            except Exception as e:
                last_error = str(e)
                delay = base_delay * (2 ** attempt)
            
            # 如果还有重试机会，等待后重试
            if attempt < retries:
                print(f"[RefreshManager] 第 {attempt + 1} 次尝试失败，{delay:.1f}秒后重试...")
                await asyncio.sleep(delay)
        
        return False, last_error
    
    def _is_rate_limit_error(self, error: Any) -> bool:
        """检查是否是限流错误（429）
        
        Args:
            error: 错误信息
            
        Returns:
            True 表示是限流错误
        """
        if isinstance(error, str):
            return "429" in error or "rate limit" in error.lower() or "请求过于频繁" in error
        return False
    
    def _get_rate_limit_delay(self, attempt: int, base_delay: float) -> float:
        """获取限流错误的等待时间
        
        429 错误使用更长的等待时间。
        
        Args:
            attempt: 当前尝试次数（从0开始）
            base_delay: 基础延迟
            
        Returns:
            等待时间（秒）
        """
        # 429 错误使用 3 倍的基础延迟
        return base_delay * 3 * (2 ** attempt)
    
    async def refresh_all_with_token(
        self,
        accounts: List['Account'],
        get_quota_func: Optional[Callable] = None,
        skip_disabled: bool = True,
        skip_error: bool = True
    ) -> RefreshProgress:
        """刷新所有账号（先刷新 Token，再获取额度）
        
        使用全局锁防止并发刷新，支持进度跟踪。
        
        Args:
            accounts: 账号列表
            get_quota_func: 获取额度的异步函数
            skip_disabled: 是否跳过已禁用的账号
            skip_error: 是否跳过已处于错误状态的账号
            
        Returns:
            刷新进度信息
        """
        # 尝试获取锁
        if not await self.acquire_refresh_lock():
            # 已有刷新在进行
            progress = self.get_progress()
            if progress:
                return progress
            # 返回一个错误状态的进度
            return RefreshProgress(
                total=0,
                status="error",
                message="刷新操作正在进行中"
            )
        
        try:
            # 过滤账号
            accounts_to_refresh = []
            for acc in accounts:
                if skip_disabled and not acc.enabled:
                    continue
                if skip_error and acc.status.value in ("unhealthy", "suspended"):
                    continue
                accounts_to_refresh.append(acc)
            
            total = len(accounts_to_refresh)
            
            # 开始刷新
            self._start_refresh(total, f"开始刷新 {total} 个账号")
            
            if total == 0:
                self._finish_refresh("completed", "没有需要刷新的账号")
                return self.get_progress()
            
            # 使用信号量控制并发
            semaphore = asyncio.Semaphore(self._config.concurrency)
            
            async def refresh_one(account: 'Account'):
                async with semaphore:
                    self._update_progress(
                        current_account=account.id,
                        message=f"正在刷新: {account.name}"
                    )
                    
                    # 使用重试机制刷新
                    success, result = await self.retry_with_backoff(
                        self.refresh_account_with_token,
                        account,
                        get_quota_func
                    )
                    
                    if success:
                        self._update_progress(success=True)
                    else:
                        self._update_progress(failed=True)
                    
                    return success, result
            
            # 并发执行
            tasks = [refresh_one(acc) for acc in accounts_to_refresh]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 完成
            self._finish_refresh("completed")
            return self.get_progress()
            
        except Exception as e:
            self._finish_refresh("error", f"刷新异常: {str(e)}")
            return self.get_progress()
            
        finally:
            self.release_refresh_lock()
    
    def _is_auth_error(self, error: Any) -> bool:
        """检查是否是认证错误（401）
        
        Args:
            error: 错误信息
            
        Returns:
            True 表示是认证错误
        """
        if isinstance(error, str):
            return "401" in error or "unauthorized" in error.lower() or "凭证已过期" in error or "需要重新登录" in error
        return False
    
    async def execute_with_auth_retry(
        self,
        account: 'Account',
        func: Callable,
        *args,
        **kwargs
    ) -> Tuple[bool, Any]:
        """执行操作，遇到 401 错误时自动刷新 Token 并重试
        
        Args:
            account: 账号对象
            func: 要执行的异步函数
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数
            
        Returns:
            (success, result) 元组
        """
        try:
            result = await func(*args, **kwargs)
            
            # 检查返回值
            if isinstance(result, tuple) and len(result) == 2:
                success, data = result
                if success:
                    return True, data
                
                # 检查是否是 401 错误
                if self._is_auth_error(data):
                    print(f"[RefreshManager] 账号 {account.id} 遇到 401 错误，尝试刷新 Token...")
                    
                    # 刷新 Token
                    refresh_success, refresh_msg = await account.refresh_token()
                    
                    if refresh_success:
                        print(f"[RefreshManager] Token 刷新成功，重试请求...")
                        # 重试原请求
                        retry_result = await func(*args, **kwargs)
                        if isinstance(retry_result, tuple) and len(retry_result) == 2:
                            return retry_result
                        return True, retry_result
                    else:
                        return False, f"Token 刷新失败: {refresh_msg}"
                
                return False, data
            
            return True, result
            
        except Exception as e:
            error_str = str(e)
            
            # 检查异常是否是 401 错误
            if self._is_auth_error(error_str):
                print(f"[RefreshManager] 账号 {account.id} 遇到 401 异常，尝试刷新 Token...")
                
                refresh_success, refresh_msg = await account.refresh_token()
                
                if refresh_success:
                    print(f"[RefreshManager] Token 刷新成功，重试请求...")
                    try:
                        retry_result = await func(*args, **kwargs)
                        if isinstance(retry_result, tuple) and len(retry_result) == 2:
                            return retry_result
                        return True, retry_result
                    except Exception as retry_e:
                        return False, f"重试失败: {str(retry_e)}"
                else:
                    return False, f"Token 刷新失败: {refresh_msg}"
            
            return False, error_str
    
    def set_accounts_getter(self, getter: Callable) -> None:
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
    
    async def start_auto_refresh(self) -> None:
        """启动自动 Token 刷新定时器
        
        定期检查所有账号的 Token 状态，自动刷新即将过期的 Token。
        启动前会清除已存在的定时器，防止重复启动。
        """
        # 先停止已存在的定时器
        await self.stop_auto_refresh()
        
        self._auto_refresh_running = True
        self._auto_refresh_task = asyncio.create_task(self._auto_refresh_loop())
        print(f"[RefreshManager] 自动 Token 刷新定时器已启动，检查间隔: {self._config.auto_refresh_interval}秒")
    
    async def stop_auto_refresh(self) -> None:
        """停止自动 Token 刷新定时器"""
        self._auto_refresh_running = False
        
        if self._auto_refresh_task:
            self._auto_refresh_task.cancel()
            try:
                await self._auto_refresh_task
            except asyncio.CancelledError:
                pass
            self._auto_refresh_task = None
            print("[RefreshManager] 自动 Token 刷新定时器已停止")
    
    def is_auto_refresh_running(self) -> bool:
        """检查自动刷新定时器是否在运行
        
        Returns:
            True 表示定时器正在运行
        """
        return self._auto_refresh_running and self._auto_refresh_task is not None
    
    async def _auto_refresh_loop(self) -> None:
        """自动刷新循环
        
        定期检查所有账号的 Token 状态，刷新即将过期的 Token。
        跳过已禁用或错误状态的账号，单个失败不影响其他账号。
        """
        while self._auto_refresh_running:
            try:
                await asyncio.sleep(self._config.auto_refresh_interval)
                
                if not self._auto_refresh_running:
                    break
                
                accounts = self._get_accounts()
                if not accounts:
                    continue
                
                # 检查需要刷新的账号
                accounts_to_refresh = []
                for account in accounts:
                    # 跳过已禁用的账号
                    if not account.enabled:
                        continue
                    
                    # 跳过错误状态的账号
                    if hasattr(account, 'status') and account.status.value in ("unhealthy", "suspended", "disabled"):
                        continue
                    
                    # 检查是否需要刷新 Token
                    if self.should_refresh_token(account):
                        accounts_to_refresh.append(account)
                
                if accounts_to_refresh:
                    print(f"[RefreshManager] 发现 {len(accounts_to_refresh)} 个账号需要刷新 Token")
                    
                    # 逐个刷新，单个失败不影响其他
                    for account in accounts_to_refresh:
                        try:
                            success, message = await self.refresh_token_if_needed(account)
                            if not success:
                                print(f"[RefreshManager] 账号 {account.id} 自动刷新失败: {message}")
                        except Exception as e:
                            print(f"[RefreshManager] 账号 {account.id} 自动刷新异常: {e}")
                            # 继续处理其他账号
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[RefreshManager] 自动刷新循环异常: {e}")
                # 继续运行，不因异常停止
    
    def get_auto_refresh_status(self) -> Dict[str, Any]:
        """获取自动刷新状态
        
        Returns:
            包含自动刷新状态信息的字典
        """
        return {
            "running": self.is_auto_refresh_running(),
            "interval": self._config.auto_refresh_interval,
            "token_refresh_before_expiry": self._config.token_refresh_before_expiry
        }


# 全局刷新管理器实例
_refresh_manager: Optional[RefreshManager] = None
_manager_lock = Lock()


def get_refresh_manager() -> RefreshManager:
    """获取全局刷新管理器实例
    
    使用单例模式，确保全局只有一个刷新管理器实例。
    
    Returns:
        全局 RefreshManager 实例
    """
    global _refresh_manager
    
    if _refresh_manager is None:
        with _manager_lock:
            # 双重检查锁定
            if _refresh_manager is None:
                _refresh_manager = RefreshManager()
    
    return _refresh_manager


def reset_refresh_manager() -> None:
    """重置全局刷新管理器
    
    主要用于测试场景，重置全局实例。
    """
    global _refresh_manager
    
    with _manager_lock:
        _refresh_manager = None
