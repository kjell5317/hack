from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase_auth.errors import AuthError, AuthRetryableError

from app.supabase_client import Supabase

bearer = HTTPBearer(auto_error=False)


class User(BaseModel):
    id: UUID
    email: str | None = None
    role: str | None = None


async def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    supabase: Supabase,
) -> User:
    if creds is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Asymmetric tokens are verified locally against the project's (cached)
    # JWKS; legacy HS256 tokens are checked with the Auth server.
    try:
        res = await supabase.auth.get_claims(jwt=creds.credentials)
    except AuthRetryableError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth unavailable") from e
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e.message}") from e
    except ValueError as e:  # supabase-auth raises pydantic errors for malformed headers
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from e
    claims = res["claims"] if res else {}
    if not claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token: no subject")
    return User(id=claims["sub"], email=claims.get("email"), role=claims.get("role"))


CurrentUser = Annotated[User, Depends(current_user)]
