import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

LAB_DATABASE_URL = os.getenv("LAB_DATABASE_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
SERVICE_TO_SERVICE_TOKEN = os.getenv("SERVICE_TO_SERVICE_TOKEN")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEZONE = os.getenv("LAB_TIMEZONE", "Asia/Kolkata")

# Booking rules (change here, not in the code)
BOOKING_DAYS_AHEAD = 7
SLOT_MINUTES = 30
HOME_START, HOME_END = "06:00", "12:00"   # home sample collection window
HOME_CAPACITY = 3                         # bookings per home slot (phlebotomists)
CENTRE_CAPACITY = 4                       # bookings per slot at each centre
HOME_LEAD_MINUTES = 120                   # earliest home slot is 2 hours from now
HOME_COLLECTION_FEE = 99
FREE_COLLECTION_ABOVE = 999               # home collection is free at or above this subtotal

for name, value in {
    "LAB_DATABASE_URL": LAB_DATABASE_URL,
    "JWT_SECRET_KEY": JWT_SECRET_KEY,
    "SERVICE_TO_SERVICE_TOKEN": SERVICE_TO_SERVICE_TOKEN,
}.items():
    if not value:
        raise RuntimeError(f"{name} is not configured")
