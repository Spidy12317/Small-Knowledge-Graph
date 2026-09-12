from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class CompletionResponse(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolCallResponse(BaseModel):
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int


class LLMBase(ABC):
    supports_tool_calling: bool = False
    llm_provider: str
    deployment: str

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> CompletionResponse:
        pass

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        temperature: float | None = None,
    ) -> ToolCallResponse:
        from core.exceptions import UnsupportedOperationError
        raise UnsupportedOperationError(
            f"Provider {self.llm_provider!r} does not support tool calling. "
            "Check supports_tool_calling before calling complete_with_tools."
        )
