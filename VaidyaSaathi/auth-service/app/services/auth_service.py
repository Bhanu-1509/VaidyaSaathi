from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS_TOKEN_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest

# Used when the email is unknown, so a failed login takes the same time either way.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


def _normalise(email: str) -> str:
    return str(email).strip().lower()


def _create_user(db: Session, full_name: str, email: str, password: str, role: str) -> User:
    email = _normalise(email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise ValueError("Email is already registered")
    user = User(
        full_name=full_name.strip(),
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, data: RegisterRequest) -> User:
    """Patients only. Reached through the verified-email flow."""
    return _create_user(db, data.full_name, str(data.email), data.password, "patient")


def create_doctor_account(db: Session, full_name: str, email: str, password: str) -> User:
    return _create_user(db, full_name, email, password, "doctor")


def create_admin_account(db: Session, full_name: str, email: str, password: str) -> User:
    return _create_user(db, full_name, email, password, "admin")


def authenticate_user(db: Session, data: LoginRequest) -> User:
    user = db.scalar(select(User).where(User.email == _normalise(str(data.email))))
    if user is None:
        verify_password(data.password, _DUMMY_HASH)
        raise ValueError("Invalid email or password")
    if not verify_password(data.password, user.password_hash):
        raise ValueError("Invalid email or password")
    if not user.is_active:
        raise ValueError("Account is inactive")
    return user


def create_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.role),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


def refresh_tokens(db: Session, data: RefreshTokenRequest) -> dict:
    payload = decode_token(data.refresh_token, "refresh")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise ValueError("Account not found or inactive")
    return create_tokens(user)
