"""历史消息管理器 - 智能压缩版

自动化管理对话历史长度，超限时智能压缩而非强硬截断：
1. 自动检测 - 发送前预估，超限时自动压缩
2. 智能压缩 - 保留最近消息 + 摘要早期对话
3. 错误恢复 - 收到超限错误后自动压缩重试
"""
import json
import time
from typing import List, Dict, Any, Tuple, Optional, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from enum import Enum


@dataclass
class SummaryCacheEntry:
    summary: str
    old_history_hash: str
    updated_at: float


class SummaryCache:
    """摘要缓存"""

    def __init__(self, max_entries: int = 64):
        self._entries: "OrderedDict[str, SummaryCacheEntry]" = OrderedDict()
        self._max_entries = max_entries

    def get(self, key: str, old_history_hash: str, max_age: int = 300) -> Optional[str]:
        entry = self._entries.get(key)
        if not entry:
            return None
        if time.time() - entry.updated_at > max_age:
            self._entries.pop(key, None)
            return None
        if entry.old_history_hash != old_history_hash:
            return None
        self._entries.move_to_end(key)
        return entry.summary

    def set(self, key: str, summary: str, old_history_hash: str):
        self._entries[key] = SummaryCacheEntry(
            summary=summary,
            old_history_hash=old_history_hash,
            updated_at=time.time()
        )
        self._entries.move_to_end(key)
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


class TruncateStrategy(str, Enum):
    """压缩策略（保留用于兼容）"""
    NONE = "none"
    AUTO_TRUNCATE = "auto_truncate"
    SMART_SUMMARY = "smart_summary"
    ERROR_RETRY = "error_retry"
    PRE_ESTIMATE = "pre_estimate"


# 自动管理的阈值常量
AUTO_COMPRESS_THRESHOLD = 120000   # 触发自动压缩的字符数阈值
SAFE_CHAR_LIMIT = 100000           # 压缩后的目标字符数
MIN_KEEP_MESSAGES = 6              # 最少保留的最近消息数
MAX_KEEP_MESSAGES = 20             # 最多保留的最近消息数
SUMMARY_MAX_LENGTH = 3000          # 摘要最大长度


@dataclass
class HistoryConfig:
    """历史消息配置（简化版，大部分参数自动管理）"""
    # 启用的策略
    strategies: List[TruncateStrategy] = field(default_factory=lambda: [TruncateStrategy.ERROR_RETRY])
    
    # 以下参数保留用于兼容，但实际使用自动值
    max_messages: int = 30
    max_chars: int = 150000
    summary_keep_recent: int = 10
    summary_threshold: int = 100000
    summary_max_length: int = 2000
    retry_max_messages: int = 20
    max_retries: int = 3
    estimate_threshold: int = 180000
    chars_per_token: float = 3.0
    summary_cache_enabled: bool = True
    summary_cache_min_delta_messages: int = 3
    summary_cache_min_delta_chars: int = 4000
    summary_cache_max_age_seconds: int = 300
    add_warning_header: bool = True
    
    def to_dict(self) -> dict:
        return {
            "strategies": [s.value for s in self.strategies],
            "max_messages": self.max_messages,
            "max_chars": self.max_chars,
            "summary_keep_recent": self.summary_keep_recent,
            "summary_threshold": self.summary_threshold,
            "summary_max_length": self.summary_max_length,
            "retry_max_messages": self.retry_max_messages,
            "max_retries": self.max_retries,
            "estimate_threshold": self.estimate_threshold,
            "chars_per_token": self.chars_per_token,
            "summary_cache_enabled": self.summary_cache_enabled,
            "summary_cache_min_delta_messages": self.summary_cache_min_delta_messages,
            "summary_cache_min_delta_chars": self.summary_cache_min_delta_chars,
            "summary_cache_max_age_seconds": self.summary_cache_max_age_seconds,
            "add_warning_header": self.add_warning_header,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "HistoryConfig":
        strategies = [TruncateStrategy(s) for s in data.get("strategies", ["error_retry"])]
        return cls(
            strategies=strategies,
            max_messages=data.get("max_messages", 30),
            max_chars=data.get("max_chars", 150000),
            summary_keep_recent=data.get("summary_keep_recent", 10),
            summary_threshold=data.get("summary_threshold", 100000),
            summary_max_length=data.get("summary_max_length", 2000),
            retry_max_messages=data.get("retry_max_messages", 20),
            max_retries=data.get("max_retries", 3),
            estimate_threshold=data.get("estimate_threshold", 180000),
            chars_per_token=data.get("chars_per_token", 3.0),
            summary_cache_enabled=data.get("summary_cache_enabled", True),
            summary_cache_min_delta_messages=data.get("summary_cache_min_delta_messages", 3),
            summary_cache_min_delta_chars=data.get("summary_cache_min_delta_chars", 4000),
            summary_cache_max_age_seconds=data.get("summary_cache_max_age_seconds", 300),
            add_warning_header=data.get("add_warning_header", True),
        )


_summary_cache = SummaryCache()


class HistoryManager:
    """历史消息管理器 - 智能压缩版"""
    
    def __init__(self, config: HistoryConfig = None, cache_key: Optional[str] = None):
        self.config = config or HistoryConfig()
        self._truncated = False
        self._truncate_info = ""
        self.cache_key = cache_key
        self._retry_count = 0
    
    @property
    def was_truncated(self) -> bool:
        return self._truncated
    
    @property
    def truncate_info(self) -> str:
        return self._truncate_info
    
    def reset(self):
        self._truncated = False
        self._truncate_info = ""

    def set_cache_key(self, key: Optional[str]):
        self.cache_key = key

    def _hash_history(self, history: List[dict]) -> str:
        """生成历史消息的简单哈希"""
        return f"{len(history)}:{len(json.dumps(history, ensure_ascii=False))}"

    def estimate_tokens(self, text: str) -> int:
        return int(len(text) / self.config.chars_per_token)
    
    def estimate_history_size(self, history: List[dict]) -> Tuple[int, int]:
        char_count = len(json.dumps(history, ensure_ascii=False))
        return len(history), char_count

    def estimate_request_chars(self, history: List[dict], user_content: str = "") -> Tuple[int, int, int]:
        history_chars = len(json.dumps(history, ensure_ascii=False))
        user_chars = len(user_content or "")
        return history_chars, user_chars, history_chars + user_chars
    
    def _extract_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif isinstance(item, str):
                    texts.append(item)
            return "\n".join(texts)
        if isinstance(content, dict):
            return content.get("text", "") or content.get("content", "")
        return str(content) if content else ""

    
    def _format_for_summary(self, history: List[dict]) -> str:
        """格式化历史消息用于生成摘要"""
        lines = []
        for msg in history:
            role = "unknown"
            content = ""
            if "userInputMessage" in msg:
                role = "user"
                content = msg.get("userInputMessage", {}).get("content", "")
            elif "assistantResponseMessage" in msg:
                role = "assistant"
                content = msg.get("assistantResponseMessage", {}).get("content", "")
            else:
                role = msg.get("role", "unknown")
                content = self._extract_text(msg.get("content", ""))
            # 截断过长的单条消息
            if len(content) > 800:
                content = content[:800] + "..."
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    def _calculate_keep_count(self, history: List[dict], target_chars: int) -> int:
        """计算应该保留多少条最近消息"""
        if not history:
            return 0
        
        # 从后往前累计，找到合适的保留数量
        total = 0
        count = 0
        for msg in reversed(history):
            msg_chars = len(json.dumps(msg, ensure_ascii=False))
            if total + msg_chars > target_chars and count >= MIN_KEEP_MESSAGES:
                break
            total += msg_chars
            count += 1
            if count >= MAX_KEEP_MESSAGES:
                break
        
        return max(MIN_KEEP_MESSAGES, min(count, len(history) - 1))

    def _build_compressed_history(
        self,
        summary: str,
        recent_history: List[dict],
        label: str = ""
    ) -> List[dict]:
        """构建压缩后的历史（摘要 + 最近消息）"""
        # 确保 recent_history 以 user 消息开头
        if recent_history and "assistantResponseMessage" in recent_history[0]:
            recent_history = recent_history[1:]
        
        # 清理孤立的 toolResults
        tool_use_ids = set()
        for msg in recent_history:
            if "assistantResponseMessage" in msg:
                for tu in msg["assistantResponseMessage"].get("toolUses", []) or []:
                    if tu.get("toolUseId"):
                        tool_use_ids.add(tu["toolUseId"])
        
        # 清理第一条 user 消息的 toolResults（因为前面没有对应的 toolUse）
        if recent_history and "userInputMessage" in recent_history[0]:
            recent_history[0]["userInputMessage"].pop("userInputMessageContext", None)
        
        # 过滤其他消息中孤立的 toolResults
        if tool_use_ids:
            for msg in recent_history:
                if "userInputMessage" in msg:
                    ctx = msg.get("userInputMessage", {}).get("userInputMessageContext", {})
                    results = ctx.get("toolResults")
                    if results:
                        filtered = [r for r in results if r.get("toolUseId") in tool_use_ids]
                        if filtered:
                            ctx["toolResults"] = filtered
                        else:
                            ctx.pop("toolResults", None)
                        if not ctx:
                            msg["userInputMessage"].pop("userInputMessageContext", None)
        else:
            for msg in recent_history:
                if "userInputMessage" in msg:
                    msg["userInputMessage"].pop("userInputMessageContext", None)

        
        # 获取 model_id
        model_id = "claude-sonnet-4"
        for msg in reversed(recent_history):
            if "userInputMessage" in msg:
                model_id = msg["userInputMessage"].get("modelId", model_id)
                break
            if "assistantResponseMessage" in msg:
                model_id = msg["assistantResponseMessage"].get("modelId", model_id)
                break
        
        # 检测消息格式
        is_kiro_format = any("userInputMessage" in h or "assistantResponseMessage" in h for h in recent_history)
        
        if is_kiro_format:
            result = [
                {
                    "userInputMessage": {
                        "content": f"[Earlier conversation summary]\n{summary}\n\n[Continuing from recent context...]",
                        "modelId": model_id,
                        "origin": "AI_EDITOR",
                    }
                },
                {
                    "assistantResponseMessage": {
                        "content": "I understand the context from the summary. Let's continue."
                    }
                }
            ]
        else:
            result = [
                {"role": "user", "content": f"[Earlier conversation summary]\n{summary}\n\n[Continuing from recent context...]"},
                {"role": "assistant", "content": "I understand the context from the summary. Let's continue."}
            ]
        
        result.extend(recent_history)
        
        if label:
            print(f"[HistoryManager] {label}: {len(recent_history)} recent + summary")
        
        return result

    async def _generate_summary(self, history: List[dict], api_caller: Callable) -> Optional[str]:
        """生成历史消息摘要"""
        if not history or not api_caller:
            return None
        
        formatted = self._format_for_summary(history)
        if len(formatted) > 15000:
            formatted = formatted[:15000] + "\n...(truncated)"
        
        prompt = f"""请简洁总结以下对话的关键信息：
1. 用户的主要目标
2. 已完成的重要操作和决策
3. 当前工作状态和关键上下文

对话历史：
{formatted}

请用中文输出摘要，控制在 {SUMMARY_MAX_LENGTH} 字符以内，重点保留对后续对话有用的信息："""
        
        try:
            summary = await api_caller(prompt)
            if summary and len(summary) > SUMMARY_MAX_LENGTH:
                summary = summary[:SUMMARY_MAX_LENGTH] + "..."
            return summary
        except Exception as e:
            print(f"[HistoryManager] 生成摘要失败: {e}")
            return None


    async def smart_compress(
        self,
        history: List[dict],
        api_caller: Callable,
        target_chars: int = SAFE_CHAR_LIMIT,
        retry_level: int = 0
    ) -> List[dict]:
        """智能压缩历史消息
        
        核心逻辑：保留最近消息 + 摘要早期对话
        
        Args:
            history: 历史消息
            api_caller: 用于生成摘要的 API 调用函数
            target_chars: 目标字符数
            retry_level: 重试级别（越高保留越少）
        """
        if not history:
            return history
        
        current_chars = len(json.dumps(history, ensure_ascii=False))
        if current_chars <= target_chars:
            return history
        
        # 根据重试级别调整保留数量
        adjusted_target = int(target_chars * (0.8 ** retry_level))
        keep_count = self._calculate_keep_count(history, adjusted_target)
        
        # 确保至少保留一些消息用于摘要
        if keep_count >= len(history):
            keep_count = max(MIN_KEEP_MESSAGES, len(history) - 2)
        
        old_history = history[:-keep_count] if keep_count < len(history) else []
        recent_history = history[-keep_count:] if keep_count > 0 else history
        
        if not old_history:
            # 没有可摘要的历史，直接返回
            return recent_history
        
        # 尝试从缓存获取摘要
        cache_key = f"{self.cache_key}:{keep_count}" if self.cache_key else None
        old_hash = self._hash_history(old_history)
        
        cached_summary = None
        if cache_key and self.config.summary_cache_enabled:
            cached_summary = _summary_cache.get(cache_key, old_hash, self.config.summary_cache_max_age_seconds)
        
        if cached_summary:
            result = self._build_compressed_history(cached_summary, recent_history, "压缩(缓存)")
            self._truncated = True
            self._truncate_info = f"智能压缩(缓存): {len(history)} -> {len(result)} 条消息"
            return result
        
        # 生成新摘要
        summary = await self._generate_summary(old_history, api_caller)
        
        if summary:
            if cache_key and self.config.summary_cache_enabled:
                _summary_cache.set(cache_key, summary, old_hash)
            
            result = self._build_compressed_history(summary, recent_history, "智能压缩")
            self._truncated = True
            self._truncate_info = f"智能压缩: {len(history)} -> {len(result)} 条消息 (摘要 {len(summary)} 字符)"
            return result
        
        # 摘要失败，回退到简单截断
        self._truncated = True
        self._truncate_info = f"摘要失败，保留最近 {len(recent_history)} 条消息"
        return recent_history


    def needs_compression(self, history: List[dict], user_content: str = "") -> bool:
        """检查是否需要压缩"""
        if not history:
            return False
        total_chars = len(json.dumps(history, ensure_ascii=False)) + len(user_content or "")
        return total_chars > AUTO_COMPRESS_THRESHOLD

    async def pre_process_async(
        self, 
        history: List[dict], 
        user_content: str = "",
        api_caller: Callable = None
    ) -> List[dict]:
        """预处理历史消息（发送前自动压缩）"""
        self.reset()
        
        if not history:
            return history
        
        # 自动检测并压缩
        if self.needs_compression(history, user_content) and api_caller:
            return await self.smart_compress(history, api_caller)
        
        return history
    
    def pre_process(self, history: List[dict], user_content: str = "") -> List[dict]:
        """预处理历史消息（同步版本，简单截断）"""
        self.reset()
        
        if not history:
            return history
        
        total_chars = len(json.dumps(history, ensure_ascii=False)) + len(user_content or "")
        if total_chars <= AUTO_COMPRESS_THRESHOLD:
            return history
        
        # 同步版本只能简单截断
        keep_count = self._calculate_keep_count(history, SAFE_CHAR_LIMIT)
        if keep_count < len(history):
            self._truncated = True
            self._truncate_info = f"预截断: {len(history)} -> {keep_count} 条消息"
            return history[-keep_count:]
        
        return history

    async def handle_length_error_async(
        self,
        history: List[dict],
        retry_count: int = 0,
        api_caller: Optional[Callable] = None
    ) -> Tuple[List[dict], bool]:
        """处理长度超限错误（智能压缩后重试）
        
        Args:
            history: 历史消息
            retry_count: 当前重试次数
            api_caller: API 调用函数
        
        Returns:
            (compressed_history, should_retry)
        """
        max_retries = self.config.max_retries
        
        if retry_count >= max_retries:
            print(f"[HistoryManager] 已达最大重试次数 ({max_retries})")
            return history, False
        
        if not history:
            return history, False
        
        self.reset()
        
        # 根据重试次数逐步减少目标大小
        target_chars = int(SAFE_CHAR_LIMIT * (0.7 ** retry_count))
        
        if api_caller:
            compressed = await self.smart_compress(
                history, api_caller, 
                target_chars=target_chars,
                retry_level=retry_count
            )
            if len(compressed) < len(history):
                self._truncate_info = f"错误重试压缩 (第 {retry_count + 1} 次): {len(history)} -> {len(compressed)} 条消息"
                return compressed, True
        else:
            # 无 api_caller，简单截断
            keep_count = max(MIN_KEEP_MESSAGES, int(len(history) * (0.5 ** (retry_count + 1))))
            if keep_count < len(history):
                truncated = history[-keep_count:]
                self._truncated = True
                self._truncate_info = f"错误重试截断 (第 {retry_count + 1} 次): {len(history)} -> {len(truncated)} 条消息"
                return truncated, True
        
        return history, False


    def handle_length_error(self, history: List[dict], retry_count: int = 0) -> Tuple[List[dict], bool]:
        """处理长度超限错误（同步版本，简单截断）"""
        max_retries = self.config.max_retries
        
        if retry_count >= max_retries:
            return history, False
        
        if not history:
            return history, False
        
        self.reset()
        
        # 根据重试次数逐步减少
        keep_ratio = 0.5 ** (retry_count + 1)
        keep_count = max(MIN_KEEP_MESSAGES, int(len(history) * keep_ratio))
        
        if keep_count < len(history):
            truncated = history[-keep_count:]
            self._truncated = True
            self._truncate_info = f"错误重试截断 (第 {retry_count + 1} 次): {len(history)} -> {len(truncated)} 条消息"
            return truncated, True
        
        return history, False
    
    def get_warning_header(self) -> Optional[str]:
        if not self.config.add_warning_header or not self._truncated:
            return None
        return self._truncate_info

    # ========== 兼容旧 API ==========
    
    def truncate_by_count(self, history: List[dict], max_count: int) -> List[dict]:
        """按消息数量截断（兼容）"""
        if len(history) <= max_count:
            return history
        original_count = len(history)
        truncated = history[-max_count:]
        self._truncated = True
        self._truncate_info = f"按数量截断: {original_count} -> {len(truncated)} 条消息"
        return truncated
    
    def truncate_by_chars(self, history: List[dict], max_chars: int) -> List[dict]:
        """按字符数截断（兼容）"""
        total_chars = len(json.dumps(history, ensure_ascii=False))
        if total_chars <= max_chars:
            return history
        
        original_count = len(history)
        result = []
        current_chars = 0
        
        for msg in reversed(history):
            msg_chars = len(json.dumps(msg, ensure_ascii=False))
            if current_chars + msg_chars > max_chars and result:
                break
            result.insert(0, msg)
            current_chars += msg_chars
        
        if len(result) < original_count:
            self._truncated = True
            self._truncate_info = f"按字符数截断: {original_count} -> {len(result)} 条消息"
        
        return result

    def should_pre_truncate(self, history: List[dict], user_content: str) -> bool:
        """兼容旧 API"""
        return self.needs_compression(history, user_content)
    
    def should_summarize(self, history: List[dict]) -> bool:
        """兼容旧 API"""
        return self.needs_compression(history)

    def should_smart_summarize(self, history: List[dict]) -> bool:
        """兼容旧 API"""
        return self.needs_compression(history)

    def should_auto_truncate_summarize(self, history: List[dict]) -> bool:
        """兼容旧 API"""
        return self.needs_compression(history)

    def should_pre_summary_for_error_retry(self, history: List[dict], user_content: str = "") -> bool:
        """兼容旧 API"""
        return self.needs_compression(history, user_content)

    async def compress_with_summary(self, history: List[dict], api_caller: Callable) -> List[dict]:
        """兼容旧 API"""
        return await self.smart_compress(history, api_caller)

    async def compress_before_auto_truncate(self, history: List[dict], api_caller: Callable) -> List[dict]:
        """兼容旧 API"""
        return await self.smart_compress(history, api_caller)

    async def generate_summary(self, history: List[dict], api_caller: Callable) -> Optional[str]:
        """兼容旧 API"""
        return await self._generate_summary(history, api_caller)

    def summarize_history_structure(self, history: List[dict], max_items: int = 12) -> str:
        """生成历史结构摘要（调试用）"""
        if not history:
            return "len=0"
        
        def entry_kind(msg):
            if "userInputMessage" in msg:
                return "U"
            if "assistantResponseMessage" in msg:
                return "A"
            role = msg.get("role")
            return "U" if role == "user" else ("A" if role == "assistant" else "?")
        
        kinds = [entry_kind(msg) for msg in history]
        if len(kinds) <= max_items:
            seq = "".join(kinds)
        else:
            head = max_items // 2
            tail = max_items - head
            seq = f"{''.join(kinds[:head])}...{''.join(kinds[-tail:])}"
        
        return f"len={len(history)} seq={seq}"



# ========== 全局配置 ==========

_history_config = HistoryConfig()


def get_history_config() -> HistoryConfig:
    """获取历史消息配置"""
    return _history_config


def set_history_config(config: HistoryConfig):
    """设置历史消息配置"""
    global _history_config
    _history_config = config


def update_history_config(data: dict):
    """更新历史消息配置"""
    global _history_config
    _history_config = HistoryConfig.from_dict(data)


def is_content_length_error(status_code: int, error_text: str) -> bool:
    """检查是否为内容长度超限错误"""
    if "CONTENT_LENGTH_EXCEEDS_THRESHOLD" in error_text:
        return True
    if "Input is too long" in error_text:
        return True
    lowered = error_text.lower()
    if "too long" in lowered and ("input" in lowered or "content" in lowered or "message" in lowered):
        return True
    if "context length" in lowered or "token limit" in lowered:
        return True
    return False
