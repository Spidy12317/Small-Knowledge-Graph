from enum import Enum


class LLMProvider(str, Enum):
    AZURE_OPENAI = "azure_openai"
    AZURE_OPENAI_GPT5 = "azure_openai_gpt5"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GROQ = "groq"
    GEMINI = "gemini"