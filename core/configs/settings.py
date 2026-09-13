from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv(override=True)


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str((Path(__file__).resolve().parents[2] / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

class GeminiSettings(CommonSettings):
    GEMINI_API_KEY: str | None = Field(default=None)
    GEMINI_MODEL: str = Field(default="gemini-3.5-flash-lite")
    MAX_CONCURRENT: int = Field(default=8)
    LLM_TEMPERATURE: float = Field(default=0)

    def is_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY and self.GEMINI_MODEL)

class AzureOpenAISettings(CommonSettings):
    AZURE_OPENAI_ENDPOINT: str | None = Field(default=None)
    AZURE_OPENAI_KEY: str | None = Field(default=None)
    AZURE_OPENAI_DEPLOYMENT: str | None = Field(default=None)
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-12-01-preview")
    MAX_CONCURRENT: int = Field(default=8)
    LLM_TEMPERATURE: float = Field(default=0)

    def is_configured(self) -> bool:
        return bool(self.AZURE_OPENAI_ENDPOINT and self.AZURE_OPENAI_KEY and self.AZURE_OPENAI_DEPLOYMENT)


class AzureGPT5Settings(CommonSettings):
    AZURE_OPENAI_ENDPOINT: str | None = Field(default=None, validation_alias="AZURE_OPENAI_GPT5_ENDPOINT")
    AZURE_OPENAI_KEY: str | None = Field(default=None, validation_alias="AZURE_OPENAI_GPT5_KEY")
    AZURE_OPENAI_DEPLOYMENT: str | None = Field(default=None, validation_alias="AZURE_OPENAI_GPT5_DEPLOYMENT")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-12-01-preview", validation_alias="AZURE_OPENAI_GPT5_API_VERSION")
    MAX_CONCURRENT: int = Field(default=8)
    LLM_TEMPERATURE: float = Field(default=0)

    def is_configured(self) -> bool:
        return bool(self.AZURE_OPENAI_ENDPOINT and self.AZURE_OPENAI_KEY and self.AZURE_OPENAI_DEPLOYMENT)


class AnthropicSettings(CommonSettings):
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    ANTHROPIC_MODEL: str = Field(default="claude-haiku-4-5-20251001")
    MAX_CONCURRENT: int = Field(default=8)
    LLM_TEMPERATURE: float = Field(default=0)

    def is_configured(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)


class OpenAISettings(CommonSettings):
    OPENAI_API_KEY: str | None = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4o")
    MAX_CONCURRENT: int = Field(default=8)
    LLM_TEMPERATURE: float = Field(default=0)

    def is_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY)


class GroqSettings(CommonSettings):
    GROQ_API_KEY: str | None = Field(default=None)
    GROQ_MODEL: str = Field(default="openai/gpt-oss-120b")
    MAX_CONCURRENT: int = Field(default=8)
    LLM_TEMPERATURE: float = Field(default=0)

    def is_configured(self) -> bool:
        return bool(self.GROQ_API_KEY)


class GraphSettings(CommonSettings):
    GRAPH_MAX_ROOT_CHILDREN: int = Field(default=4)
    GRAPH_MAX_NODE_CHILDREN: int = Field(default=8)
    GRAPH_MAX_CONCURRENT_EVALUATIONS: int = Field(default=1)
    GRAPH_HIGH_CONFIDENCE_SCORE_THRESHOLD: float = Field(default=0.70)
    GRAPH_MAX_CONCURRENT_INSERTIONS: int = Field(default=4)


class DatabaseSettings(CommonSettings):
    POSTGRES_HOST: str | None = Field(default=None)
    POSTGRES_DB: str | None = Field(default=None)
    POSTGRES_USER: str | None = Field(default=None)
    POSTGRES_PASSWORD: str | None = Field(default=None)
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_SSLMODE: bool = Field(default=False)
    POSTGRES_CONNECT_TIMEOUT: int = Field(default=5)
    POSTGRES_STATEMENT_TIMEOUT_MS: int = Field(default=15_000)
    DATABASE_ECHO: bool = Field(default=False)

    def is_configured(self) -> bool:
        return bool(self.POSTGRES_HOST and self.POSTGRES_DB and self.POSTGRES_USER)

    @property
    def database_url(self) -> str:
        user = quote_plus(self.POSTGRES_USER or "")
        password = quote_plus(self.POSTGRES_PASSWORD or "")
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def connect_args(self) -> dict:
        return {
            "timeout": self.POSTGRES_CONNECT_TIMEOUT,
            "ssl": self.POSTGRES_SSLMODE,
            "server_settings": {"statement_timeout": str(self.POSTGRES_STATEMENT_TIMEOUT_MS)},
        }


class OtelSettings(CommonSettings):
    OTEL_ENABLED: bool = Field(default=False)
    OTEL_SERVICE_NAME: str = Field(default="skg")
    OTEL_TRACES_FILE: str = Field(default="data/traces.jsonl")
    OTEL_MAX_CONTENT_LENGTH: int = Field(default=100_000)


class ConfigManager:
    _gemini_settings: GeminiSettings | None = None
    _azure_openai_settings: AzureOpenAISettings | None = None
    _azure_gpt5_settings: AzureGPT5Settings | None = None
    _anthropic_settings: AnthropicSettings | None = None
    _openai_settings: OpenAISettings | None = None
    _groq_settings: GroqSettings | None = None
    _graph_settings: GraphSettings | None = None
    _database_settings: DatabaseSettings | None = None
    _otel_settings: OtelSettings | None = None

    @property
    def gemini_settings(self) -> GeminiSettings:
        if self._gemini_settings is None:
            self._gemini_settings = GeminiSettings()
        return self._gemini_settings

    @property
    def azure_openai_settings(self) -> AzureOpenAISettings:
        if self._azure_openai_settings is None:
            self._azure_openai_settings = AzureOpenAISettings()
        return self._azure_openai_settings

    @property
    def azure_gpt5_settings(self) -> AzureGPT5Settings:
        if self._azure_gpt5_settings is None:
            self._azure_gpt5_settings = AzureGPT5Settings()
        return self._azure_gpt5_settings

    @property
    def anthropic_settings(self) -> AnthropicSettings:
        if self._anthropic_settings is None:
            self._anthropic_settings = AnthropicSettings()
        return self._anthropic_settings

    @property
    def openai_settings(self) -> OpenAISettings:
        if self._openai_settings is None:
            self._openai_settings = OpenAISettings()
        return self._openai_settings

    @property
    def groq_settings(self) -> GroqSettings:
        if self._groq_settings is None:
            self._groq_settings = GroqSettings()
        return self._groq_settings

    @property
    def graph_settings(self) -> GraphSettings:
        if self._graph_settings is None:
            self._graph_settings = GraphSettings()
        return self._graph_settings

    @property
    def database_settings(self) -> DatabaseSettings:
        if self._database_settings is None:
            self._database_settings = DatabaseSettings()
        return self._database_settings

    @property
    def otel_settings(self) -> OtelSettings:
        if self._otel_settings is None:
            self._otel_settings = OtelSettings()
        return self._otel_settings


config = ConfigManager()


def get_azure_openai_settings() -> AzureOpenAISettings:
    return config.azure_openai_settings

def get_gemini_settings() -> GeminiSettings:
    return config.gemini_settings

def get_azure_gpt5_settings() -> AzureGPT5Settings:
    return config.azure_gpt5_settings

def get_anthropic_settings() -> AnthropicSettings:
    return config.anthropic_settings

def get_openai_settings() -> OpenAISettings:
    return config.openai_settings

def get_groq_settings() -> GroqSettings:
    return config.groq_settings

def get_graph_settings() -> GraphSettings:
    return config.graph_settings

def get_database_settings() -> DatabaseSettings:
    return config.database_settings

def get_otel_settings() -> OtelSettings:
    return config.otel_settings