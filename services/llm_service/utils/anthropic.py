import asyncio
import logging
from typing import Any

from anthropic import AsyncAnthropic

from core.configs.settings import get_anthropic_settings
from core.exceptions import ConfigurationError, LLMRequestError
from services.llm_service.models import CompletionResponse, ToolCall, ToolCallResponse

logger = logging.getLogger(__name__)


class AnthropicClient:
    supports_tool_calling = True

    def __init__(self, settings=None, model: str | None = None, temperature: float | None = None):
        if settings is None:
            settings = get_anthropic_settings()

        if not settings.is_configured():
            raise ConfigurationError(
                "Anthropic is not configured. Set ANTHROPIC_API_KEY."
            )

        self._settings = settings
        self._model = model or settings.ANTHROPIC_MODEL
        self._temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT)
        logger.debug("AnthropicClient ready | model=%s", self._model)

    @property
    def deployment(self) -> str:
        return self._model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> CompletionResponse:
        temp = temperature if temperature is not None else self._temperature
        async with self._semaphore:
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=8096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=temp,
                )
            except Exception as e:
                logger.error("Anthropic request failed | model=%s error=%s", self._model, e)
                raise LLMRequestError(f"Anthropic request failed: {e}", original_error=e) from e

        content = response.content[0].text
        return CompletionResponse(
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        temperature: float | None = None,
    ) -> ToolCallResponse:
        temp = temperature if temperature is not None else self._temperature
        async with self._semaphore:
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=8096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    tools=tools,
                    temperature=temp,
                )
            except Exception as e:
                logger.error("Anthropic tool call failed | model=%s error=%s", self._model, e)
                raise LLMRequestError(f"Anthropic tool call failed: {e}", original_error=e) from e

        tool_calls = [
            ToolCall(id=block.id, name=block.name, arguments=block.input)
            for block in response.content
            if block.type == "tool_use"
        ]
        return ToolCallResponse(
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
