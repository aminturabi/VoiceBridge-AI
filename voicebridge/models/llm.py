"""LLM / Translation Provider abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from voicebridge.pipeline.contracts.schemas import LlmRequest, LlmResponse


class BaseLLM(ABC):
    """Abstract base class for Large Language Model & Machine Translation providers."""

    name: str = "base_llm"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend service or model is available."""
        pass

    @abstractmethod
    def process_text(self, request: LlmRequest) -> LlmResponse:
        """Process/translate text using LlmRequest and return LlmResponse."""
        pass
