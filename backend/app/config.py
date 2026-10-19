from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    # Secret key (sb_secret_..., or the legacy service_role key). Server-side
    # only: it bypasses RLS, so the backend must scope queries itself.
    supabase_secret_key: str


settings = Settings()
