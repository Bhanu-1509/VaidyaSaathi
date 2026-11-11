import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import JWT_SECRET_KEY, NOTIFICATION_SERVICE_URL, SERVICE_TO_SERVICE_TOKEN
from app.models.email_otp import EmailOtp
from app.models.user import User

OTP_TTL_SECONDS = 600
RESEND_SECONDS = 60
MAX_ATTEMPTS = 5
REGISTRATION_TOKEN_MINUTES = 15


class OtpError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hash(email: str, code: str) -> str:
    return hmac.new(JWT_SECRET_KEY.encode(), f"otp:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _send(email: str, name: str, code: str) -> str:
    """Ask notification-service to email the code. Returns "sent" or "logged" (console mode)."""
    body = json.dumps(
        {"to": email, "template": "otp", "data": {"name": name, "code": code, "minutes": OTP_TTL_SECONDS // 60}}
    ).encode()
    req = urllib.request.Request(
        f"{NOTIFICATION_SERVICE_URL}/notifications/email",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Service-Token": SERVICE_TO_SERVICE_TOKEN},
    )
    try:
        reply = urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}").get("detail")
        except ValueError:
            detail = None
        if exc.code == 401:
            detail = "The notification service rejected this service's token. SERVICE_TO_SERVICE_TOKEN must match."
        raise OtpError(f"Could not send the verification email. {detail or ''}".strip(), 503) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise OtpError("Could not reach the notification service. Make sure it is running.", 503) from exc
    try:
        return json.loads(reply).get("status", "sent")
    except ValueError:
        return "sent"


def request_otp(db: Session, email: str, full_name: str) -> tuple[str, str]:
    """Create and send a code. Returns (delivery, code); delivery is "sent" or "logged"."""
    email = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise OtpError("Email is already registered", 409)

    now = datetime.now(timezone.utc)
    row = db.scalar(select(EmailOtp).where(EmailOtp.email == email))
    if row and (now - _aware(row.last_sent_at)).total_seconds() < RESEND_SECONDS:
        raise OtpError("Please wait a minute before requesting another code", 429)

    code = f"{secrets.randbelow(10**6):06d}"
    if row is None:
        row = EmailOtp(email=email)
        db.add(row)
    row.code_hash = _hash(email, code)
    row.expires_at = now + timedelta(seconds=OTP_TTL_SECONDS)
    row.last_sent_at = now
    row.attempts = 0
    db.commit()

    try:
        delivery = _send(email, full_name.strip(), code)
    except OtpError:
        db.execute(delete(EmailOtp).where(EmailOtp.email == email))
        db.commit()
        raise
    return delivery, code


def verify_otp(db: Session, email: str, code: str) -> str:
    """Check the code; on success return a short-lived registration token."""
    email = email.strip().lower()
    row = db.scalar(select(EmailOtp).where(EmailOtp.email == email))
    now = datetime.now(timezone.utc)

    if row is None:
        raise OtpError("Request a verification code first")
    if _aware(row.expires_at) < now:
        db.delete(row)
        db.commit()
        raise OtpError("This code has expired. Request a new one")
    if row.attempts >= MAX_ATTEMPTS:
        db.delete(row)
        db.commit()
        raise OtpError("Too many wrong attempts. Request a new code", 429)
    if not hmac.compare_digest(row.code_hash, _hash(email, code)):
        row.attempts += 1
        db.commit()
        raise OtpError("Incorrect code")

    db.delete(row)
    db.commit()
    return jwt.encode(
        {
            "type": "register",
            "email": email,
            "iat": now,
            "exp": now + timedelta(minutes=REGISTRATION_TOKEN_MINUTES),
        },
        JWT_SECRET_KEY,
        algorithm="HS256",
    )


def decode_registration_token(token: str) -> str:
    payload = jwt.decode(
        token, JWT_SECRET_KEY, algorithms=["HS256"], options={"require": ["email", "iat", "exp", "type"]}
    )
    if payload.get("type") != "register":
        raise jwt.InvalidTokenError("Registration token required")
    return payload["email"]
