"""
Abstract base class for text generation providers
"""
from abc import ABC, abstractmethod
from typing import Optional, Callable


class TextProvider(ABC):
    """Abstract base class for text generation"""

    def __init__(self):
        # 存储最后一次调用的 tokens 使用量
        self.last_total_tokens: int = 0
        # 可选的回调函数，在每次生成后调用
        self._usage_callback: Optional[Callable[[int], None]] = None

    def set_usage_callback(self, callback: Callable[[int], None]):
        """设置使用量回调函数"""
        self._usage_callback = callback

    def _report_usage(self, total_tokens: int):
        """报告 tokens 使用量"""
        self.last_total_tokens = total_tokens
        if self._usage_callback:
            self._usage_callback(total_tokens)

    @abstractmethod
    def generate_text(self, prompt: str, thinking_budget: int = 1000) -> str:
        """
        Generate text content from prompt

        Args:
            prompt: The input prompt for text generation
            thinking_budget: Budget for thinking/reasoning (provider-specific)

        Returns:
            Generated text content
        """
        pass
