from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    # Secret key (sb_secret_..., or the legacy service_role key). Server-side
    # only: it bypasses RLS, so the backend must scope queries itself.
    supabase_secret_key: str

    # LLM provider for Haystack. API keys are read from OPENAI_API_KEY or
    # GOOGLE_API_KEY. "none" runs without keys: keyword-hash embeddings, no /ask.
    llm_provider: Literal["openai", "gemini", "none"] = "none"
    # Empty uses the Haystack integration's default chat model.
    chat_model: str = ""

    # Langfuse tracing is on when both keys are set (LANGFUSE_BASE_URL picks the region).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""


settings = Settings()
