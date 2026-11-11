import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# 3.5 Flash-Lite is Google's cheapest current model. Use gemini-3.8-flash for better answers.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

DOCTOR_SERVICE_URL = os.getenv("DOCTOR_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
SCHEDULING_SERVICE_URL = os.getenv("SCHEDULING_SERVICE_URL", "http://127.0.0.1:8004").rstrip("/")
LAB_SERVICE_URL = os.getenv("LAB_SERVICE_URL", "http://127.0.0.1:8006").rstrip("/")
TIMEZONE = os.getenv("AI_TIMEZONE", "Asia/Kolkata")

MAX_TOOL_ROUNDS = 6
MAX_HISTORY = 24
REQUESTS_PER_MINUTE = int(os.getenv("AI_REQUESTS_PER_MINUTE", "20"))
