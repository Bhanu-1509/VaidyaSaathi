import hmac
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, EmailStr

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SERVICE_TOKEN = os.getenv("SERVICE_TO_SERVICE_TOKEN")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
# Gmail shows app passwords in groups of four ("abcd efgh ijkl mnop"); the spaces are not part of it.
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
SMTP_FROM = (os.getenv("SMTP_FROM") or "").strip() or SMTP_USER

if not SERVICE_TOKEN:
    raise RuntimeError("SERVICE_TO_SERVICE_TOKEN is not configured")

log = logging.getLogger("notification")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="VaidyaSaathi Notification Service", version="1.0.0")


class EmailRequest(BaseModel):
    to: EmailStr
    template: Literal["otp", "message"]
    data: dict[str, Any] = {}


def render(template: str, data: dict[str, Any]) -> tuple[str, str]:
    """Return (subject, plain-text body)."""
    if template == "otp":
        name = str(data.get("name") or "there")
        code = str(data.get("code", ""))
        minutes = int(data.get("minutes", 10))
        return (
            f"{code} is your VaidyaSaathi verification code",
            f"Hello {name},\n\nYour VaidyaSaathi verification code is {code}.\n"
            f"It expires in {minutes} minutes. If you did not try to register, ignore this email.\n\n"
            "VaidyaSaathi",
        )
    return str(data.get("subject", "VaidyaSaathi")), str(data.get("body", ""))


def deliver(to: str, subject: str, body: str) -> str:
    if not SMTP_HOST:
        # Console mode for local development: nothing leaves the machine.
        log.warning("EMAIL (console mode) to=%s subject=%s\n%s", to, subject, body)
        return "logged"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP_FROM, to, subject
    msg.set_content(body)
    if SMTP_PORT == 465:  # implicit TLS
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
    else:                 # 587: plain connection upgraded with STARTTLS
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    with server as s:
        if SMTP_PORT != 465:
            s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)
    log.info("Email sent to %s (%s)", to, subject)
    return "sent"


@app.post("/notifications/email", status_code=status.HTTP_202_ACCEPTED)
def send_email(
    data: EmailRequest,
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
):
    if not x_service_token or not hmac.compare_digest(x_service_token, SERVICE_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service credentials")
    subject, body = render(data.template, data.data)
    try:
        return {"status": deliver(str(data.to), subject, body)}
    except smtplib.SMTPAuthenticationError as exc:
        log.error("SMTP login failed for %s: %s", SMTP_USER, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The email account rejected the login. For Gmail, SMTP_PASSWORD must be a 16-letter App Password "
            "(Google Account > Security > App passwords), not your normal password.",
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        log.error("Recipient refused %s: %s", data.to, exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The email address was refused. Check it and try again.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        log.error("SMTP failure via %s:%s: %r", SMTP_HOST, SMTP_PORT, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Could not send email through {SMTP_HOST}:{SMTP_PORT}. Check SMTP_HOST, SMTP_PORT and the internet connection.",
        ) from exc


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "mode": "smtp" if SMTP_HOST else "console"}
