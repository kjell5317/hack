import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["anthropic", "openai", "gemini", "none"]
EmbeddingProvider = Literal["openai", "gemini", "hash"]

# The SDKs read these themselves and treat an empty value as a URL, which
# breaks every call. An empty line in .env shouldn't do that.
for _var in ("OPENAI_BASE_URL", "ANTHROPIC_BASE_URL"):
    if os.environ.get(_var) == "":
        del os.environ[_var]


class Settings(BaseSettings):
    # Empty values in .env count as unset, so defaults apply.
    model_config = SettingsConfigDict(env_ignore_empty=True)

    supabase_url: str
    # Secret key (sb_secret_..., or the legacy service_role key). Server-side
    # only: it bypasses RLS, so the backend must scope queries itself.
    supabase_secret_key: str

    # "auto" uses the first provider whose key is set (see llm_provider_resolved).
    llm_provider: Literal["auto", "anthropic", "openai", "gemini", "none"] = "auto"
    # Empty uses the provider default (see app/core/ai/providers.py).
    chat_model: str = ""
    # "auto": OpenAI or Gemini when their key is set, else keyword hashing.
    # Anthropic has no embeddings API.
    embedding_provider: Literal["auto", "openai", "gemini", "hash"] = "auto"

    # Read here only to detect which provider is configured; the Haystack
    # components read the same env vars themselves.
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # Langfuse tracing is on when both keys are set (LANGFUSE_BASE_URL picks the region).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    @property
    def llm_provider_resolved(self) -> LlmProvider:
        # Keep in sync with llm_summary() in scripts/hack.py.
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        if self.google_api_key:
            return "gemini"
        return "none"

    @property
    def embedding_provider_resolved(self) -> EmbeddingProvider:
        if self.embedding_provider != "auto":
            return self.embedding_provider
        if self.openai_api_key:
            return "openai"
        if self.google_api_key:
            return "gemini"
        return "hash"

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


settings = Settings()
