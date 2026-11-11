import os
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_FILE)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
AUTH_DATABASE_URL = os.getenv("AUTH_DATABASE_URL")
SERVICE_TO_SERVICE_TOKEN = os.getenv("SERVICE_TO_SERVICE_TOKEN")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://127.0.0.1:8005")
# When email is not configured (notification-service in console mode), show the sign-up code on screen
# so local testing works. Ignored once SMTP is set up: then the code is only ever emailed.
SHOW_DEV_OTP = os.getenv("SHOW_DEV_OTP", "true").strip().lower() in {"1", "true", "yes"}

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not configured")

if not AUTH_DATABASE_URL:
    raise RuntimeError("AUTH_DATABASE_URL is not configured")


if not SERVICE_TO_SERVICE_TOKEN:
    raise RuntimeError("SERVICE_TO_SERVICE_TOKEN is not configured")
