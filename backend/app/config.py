from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Defaults match `supabase start`. For hosted Supabase use the *session pooler*
    # connection string (the direct db.<ref>.supabase.co host is IPv6-only).
    database_url: str = "postgresql://postgres:postgres@localhost:54322/postgres"
    supabase_url: str = ""
    # Only needed while tokens are signed with the legacy HS256 secret
    # (local `supabase start`, older hosted projects). Asymmetric keys use JWKS.
    supabase_jwt_secret: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        scheme, rest = self.database_url.split("://", 1)
        return f"postgresql+asyncpg://{rest}"


settings = Settings()
