import asyncio
import logging
from typing import Any
import uuid

from google import genai
from google.genai import types

from core.configs.settings import get_gemini_settings
from core.exceptions import ConfigurationError, LLMRequestError
from services.llm_service.models import CompletionResponse, ToolCall, ToolCallResponse

logger = logging.getLogger(__name__)


class GeminiClient:
    supports_tool_calling = True

    def __init__(
        self,
        settings=None,
        model: str | None = None,
        temperature: float | None = None,
    ):
        if settings is None:
            settings = get_gemini_settings()

        if not settings.is_configured():
            raise ConfigurationError(
                "Gemini is not configured. Set GEMINI_API_KEY."
            )

        self._settings = settings
        self._model = model or settings.GEMINI_MODEL
        self._temperature = (
            temperature if temperature is not None else settings.LLM_TEMPERATURE
        )
        # Initializes client targeting the modern Gemini API
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT)
        logger.debug("GeminiClient ready | model=%s", self._model)

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
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temp,
        )

        async with self._semaphore:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=user_prompt,
                    config=config,
                )
            except Exception as e:
                logger.error(
                    "Gemini request failed | model=%s error=%s", self._model, e
                )
                raise LLMRequestError(f"Gemini request failed: {e}", original_error=e) from e

        content = (response.text or "").strip()
        usage = response.usage_metadata

        return CompletionResponse(
            content=content,
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
        )

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        temperature: float | None = None,
    ) -> ToolCallResponse:
        temp = temperature if temperature is not None else self._temperature

        function_declarations = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t.get("input_schema"),
            )
            for t in tools
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temp,
            tools=[types.Tool(function_declarations=function_declarations)],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingMode.AUTO
                )
            ),
        )

        async with self._semaphore:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=user_prompt,
                    config=config,
                )
            except Exception as e:
                logger.error(
                    "Gemini tool call failed | model=%s error=%s", self._model, e
                )
                raise LLMRequestError(
                    f"Gemini tool call failed: {e}", original_error=e
                ) from e

        tool_calls: list[ToolCall] = []

        # Parse function calls from response candidates
        if response.function_calls:
            for call in response.function_calls:
                tool_calls.append(
                    ToolCall(
                        # Gemini function calls don't return call IDs; generate UUID for downstream tracking
                        id=str(uuid.uuid4()),
                        name=call.name,
                        arguments=dict(call.args) if call.args else {},
                    )
                )

        usage = response.usage_metadata
        return ToolCallResponse(
            tool_calls=tool_calls,
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
        )