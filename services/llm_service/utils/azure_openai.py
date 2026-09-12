import asyncio
import json
import logging
from typing import Any

from openai import AsyncAzureOpenAI

from core.configs.settings import get_azure_openai_settings
from core.exceptions import ConfigurationError, LLMRequestError
from services.llm_service.models import CompletionResponse, ToolCall, ToolCallResponse

logger = logging.getLogger(__name__)


class AzureOpenAIClient:
    supports_tool_calling = True

    def __init__(self, settings=None, model: str | None = None, temperature: float | None = None):
        if settings is None:
            settings = get_azure_openai_settings()

        if not settings.is_configured():
            raise ConfigurationError(
                "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, and AZURE_OPENAI_DEPLOYMENT."
            )

        self._settings = settings
        self._model = model or settings.AZURE_OPENAI_DEPLOYMENT
        self._temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT)
        logger.debug("AzureOpenAIClient ready | model=%s", self._model)

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
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                )
            except Exception as e:
                logger.error("Azure OpenAI request failed | model=%s error=%s", self._model, e)
                raise LLMRequestError(f"Azure OpenAI request failed: {e}", original_error=e) from e

        content = response.choices[0].message.content.strip()
        usage = response.usage
        return CompletionResponse(
            content=content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        temperature: float | None = None,
    ) -> ToolCallResponse:
        temp = temperature if temperature is not None else self._temperature
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        async with self._semaphore:
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=openai_tools,
                    tool_choice="auto",
                    temperature=temp,
                )
            except Exception as e:
                logger.error("Azure OpenAI tool call failed | model=%s error=%s", self._model, e)
                raise LLMRequestError(f"Azure OpenAI tool call failed: {e}", original_error=e) from e

        message = response.choices[0].message
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        usage = response.usage
        return ToolCallResponse(
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
