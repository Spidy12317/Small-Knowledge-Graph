import logging
from typing import Any

from core import config, enums
from core.exceptions import ConfigurationError, UnsupportedOperationError
from services.llm_service.models import LLMBase, CompletionResponse, ToolCallResponse
from services.llm_service.utils.azure_openai import AzureOpenAIClient
from services.llm_service.utils.anthropic import AnthropicClient
from services.llm_service.utils.openai import OpenAIClient
from services.llm_service.utils.groq import GroqClient
from services.llm_service.utils.gemini import GeminiClient

logger = logging.getLogger(__name__)


class LLMService(LLMBase):
    def __init__(
        self,
        provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
        model: str | None = None,
        temperature: float | None = None,
    ):
        match provider:
            case enums.LLMProvider.AZURE_OPENAI:
                self._client = AzureOpenAIClient(model=model, temperature=temperature)
            case enums.LLMProvider.AZURE_OPENAI_GPT5:
                self._client = AzureOpenAIClient(
                    settings=config.azure_gpt5_settings, model=model, temperature=temperature
                )
            case enums.LLMProvider.ANTHROPIC:
                self._client = AnthropicClient(model=model, temperature=temperature)
            case enums.LLMProvider.OPENAI:
                self._client = OpenAIClient(model=model, temperature=temperature)
            case enums.LLMProvider.GROQ:
                self._client = GroqClient(model=model, temperature=temperature)
            case enums.LLMProvider.GEMINI:
                self._client = GeminiClient(model=model, temperature=temperature)
            case _:
                raise ConfigurationError(f"Unsupported LLM provider: {provider!r}")

        self.provider = provider
        self.llm_provider = provider.value
        self.deployment = self._client.deployment
        logger.info("LLMService ready | provider=%s model=%s", self.llm_provider, self.deployment)

    @property
    def supports_tool_calling(self) -> bool:
        return self._client.supports_tool_calling

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> CompletionResponse:
        return await self._client.complete(system_prompt, user_prompt, temperature)

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        temperature: float | None = None,
    ) -> ToolCallResponse:
        if not self.supports_tool_calling:
            raise UnsupportedOperationError(
                f"Provider {self.llm_provider!r} does not support tool calling."
            )
        return await self._client.complete_with_tools(system_prompt, user_prompt, tools, temperature)
