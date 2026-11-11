"""Token checks, matching the other VaidyaSaathi services."""
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import AUTH_SERVICE_URL, JWT_SECRET_KEY, SERVICE_TO_SERVICE_TOKEN

bearer = HTTPBearer(auto_error=False)


def _current_user(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", {"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp", "type", "role"]},
        )
        if payload["type"] != "access":
            raise ValueError
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired access token", {"WWW-Authenticate": "Bearer"}
        )

    # Make sure the account still exists and is active.
    try:
        r = httpx.get(
            f"{AUTH_SERVICE_URL}/auth/internal/users/{user_id}/status",
            headers={"X-Service-Token": SERVICE_TO_SERVICE_TOKEN},
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth Service is unavailable")
    if r.status_code == 404:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User account not found")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not verify the user account")
    account = r.json()
    if account.get("is_active") is not True:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is inactive")
    return {"user_id": user_id, "role": account.get("role")}


def require_patient(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    user = _current_user(credentials)
    if user["role"] != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only patients can book lab tests")
    return user


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    user = _current_user(credentials)
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
