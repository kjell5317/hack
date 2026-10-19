from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

bearer = HTTPBearer(auto_error=False)


class User(BaseModel):
    id: UUID
    email: str | None = None
    role: str | None = None


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


def decode_token(token: str) -> dict[str, Any]:
    """Verify a Supabase access token and return its claims.

    Asymmetric tokens (ES256/RS256) are checked against the project's JWKS,
    legacy HS256 tokens against SUPABASE_JWT_SECRET.
    """
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise jwt.InvalidTokenError("HS256 token but SUPABASE_JWT_SECRET is unset")
        key: Any = settings.supabase_jwt_secret
    elif alg in ("ES256", "RS256"):
        if not settings.supabase_url:
            raise jwt.InvalidTokenError("SUPABASE_URL is unset, cannot fetch JWKS")
        key = _jwks_client().get_signing_key_from_jwt(token).key
    else:
        raise jwt.InvalidTokenError(f"Unsupported algorithm: {alg}")
    return jwt.decode(token, key, algorithms=[alg], audience="authenticated")


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    # Sync on purpose: FastAPI runs it in a threadpool, so the (cached) JWKS
    # fetch never blocks the event loop.
    if creds is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    return User(id=claims["sub"], email=claims.get("email"), role=claims.get("role"))


CurrentUser = Annotated[User, Depends(current_user)]
