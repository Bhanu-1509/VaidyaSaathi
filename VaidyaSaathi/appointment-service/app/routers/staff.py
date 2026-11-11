"""Appointment views for doctors and admins.

Doctors see only their own appointments; admins see everyone's. Each row
includes the patient's name, email, phone, gender and age, looked up from
auth-service and patient-service with the shared service token.
"""
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import AUTH_SERVICE_URL, JWT_SECRET_KEY, PATIENT_SERVICE_URL, SERVICE_TO_SERVICE_TOKEN
from app.database import get_db
from app.models.appointment import Appointment

DOCTOR_SERVICE_URL = os.getenv("DOCTOR_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
IST = ZoneInfo("Asia/Kolkata")
MAX_RANGE_DAYS = 62

router = APIRouter(prefix="/appointments/staff", tags=["Doctor and admin views"])
bearer = HTTPBearer(auto_error=False)
SVC = {"X-Service-Token": SERVICE_TO_SERVICE_TOKEN}


# ---------------- auth ----------------
def current_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    """Return {"user_id", "role", "doctor_id"} for an active doctor or admin."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", {"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=["HS256"],
                             options={"require": ["sub", "exp", "type", "role"]})
        if payload["type"] != "access":
            raise ValueError
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired access token", {"WWW-Authenticate": "Bearer"})

    try:
        r = httpx.get(f"{AUTH_SERVICE_URL}/auth/internal/users/{user_id}/status", headers=SVC, timeout=5.0)
    except httpx.RequestError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth Service is unavailable")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    account = r.json()
    role = account.get("role")
    if account.get("is_active") is not True or role not in {"doctor", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only doctors and admins can open this page")

    doctor_id = None
    if role == "doctor":
        try:
            docs = httpx.get(f"{DOCTOR_SERVICE_URL}/doctors/", timeout=5.0).json()
        except (httpx.RequestError, ValueError):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Doctor Service is unavailable")
        doctor_id = next((d["id"] for d in docs if d.get("auth_user_id") == user_id), None)
        if doctor_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Your doctor profile has not been created yet")
    return {"user_id": user_id, "role": role, "doctor_id": doctor_id}


Staff = Annotated[dict, Depends(current_staff)]
DB = Annotated[Session, Depends(get_db)]


# ---------------- helpers ----------------
def _range(on: date | None, start: date | None, end: date | None) -> tuple[datetime, datetime]:
    if on:
        start = end = on
    start = start or datetime.now(IST).date()
    end = end or start
    if end < start:
        raise HTTPException(422, "End date is before start date")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(422, f"Choose a range of at most {MAX_RANGE_DAYS} days")
    return datetime.combine(start, time(0), IST), datetime.combine(end + timedelta(days=1), time(0), IST)


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    born, today = date.fromisoformat(dob[:10]), datetime.now(IST).date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _patients(ids: set[int]) -> dict[int, dict]:
    """Names from auth-service, contact details from patient-service. Missing data is left blank."""
    if not ids:
        return {}
    q = {"ids": ",".join(map(str, sorted(ids)))}
    out = {i: {"id": i, "name": f"Patient #{i}", "email": None, "phone": None, "gender": None, "age": None} for i in ids}
    try:
        for u in httpx.get(f"{AUTH_SERVICE_URL}/auth/internal/users", params=q, headers=SVC, timeout=5.0).json():
            out[u["id"]].update(name=u["full_name"], email=u["email"])
    except (httpx.RequestError, ValueError, KeyError, TypeError):
        pass
    try:
        for p in httpx.get(f"{PATIENT_SERVICE_URL}/patients/internal/profiles", params=q, headers=SVC, timeout=5.0).json():
            out[p["auth_user_id"]].update(phone=p["phone_number"], gender=p["gender"], age=_age(p["date_of_birth"]))
    except (httpx.RequestError, ValueError, KeyError, TypeError):
        pass
    return out


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _row(a: Appointment, patient: dict) -> dict:
    return {
        "id": a.id,
        "doctor_id": a.doctor_id,
        "start_time": _aware(a.start_time).isoformat(),
        "end_time": _aware(a.end_time).isoformat(),
        "status": a.status,
        "reason": a.reason,
        "cancellation_reason": a.cancellation_reason,
        "created_at": _aware(a.created_at).isoformat(),
        "patient": patient,
    }


def _scope(stmt, staff: dict, doctor_id: int | None):
    if staff["role"] == "doctor":
        return stmt.where(Appointment.doctor_id == staff["doctor_id"])
    return stmt.where(Appointment.doctor_id == doctor_id) if doctor_id else stmt


# ---------------- routes ----------------
@router.get("")
def list_appointments(
    staff: Staff,
    db: DB,
    on: Annotated[date | None, Query(alias="date")] = None,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    doctor_id: Annotated[int | None, Query(gt=0)] = None,
    status_filter: Annotated[Literal["booked", "confirmed", "cancelled", "completed"] | None, Query(alias="status")] = None,
):
    lo, hi = _range(on, start, end)
    stmt = _scope(select(Appointment), staff, doctor_id).where(Appointment.start_time >= lo, Appointment.start_time < hi)
    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)
    rows = db.scalars(stmt.order_by(Appointment.start_time).limit(1000)).all()
    people = _patients({a.patient_auth_user_id for a in rows})
    return [_row(a, people[a.patient_auth_user_id]) for a in rows]


@router.get("/summary")
def daily_summary(
    staff: Staff,
    db: DB,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    doctor_id: Annotated[int | None, Query(gt=0)] = None,
):
    """Appointments per day, for the date strip: [{date, total, active}]."""
    lo, hi = _range(None, start, end)
    stmt = _scope(select(Appointment.start_time, Appointment.status), staff, doctor_id).where(
        Appointment.start_time >= lo, Appointment.start_time < hi)
    days: dict[str, dict] = {}
    for start_time, st in db.execute(stmt):
        d = _aware(start_time).astimezone(IST).date().isoformat()
        e = days.setdefault(d, {"date": d, "total": 0, "active": 0, "completed": 0, "cancelled": 0})
        e["total"] += 1
        if st in ("booked", "confirmed"):
            e["active"] += 1
        elif st in ("completed", "cancelled"):
            e[st] += 1
    return sorted(days.values(), key=lambda x: x["date"])


@router.get("/stats")
def stats(staff: Staff, db: DB):
    """Headline numbers for the admin dashboard (doctors get their own numbers)."""
    today = datetime.now(IST).date()
    lo, hi = _range(today, None, None)
    base = _scope(select(func.count()).select_from(Appointment), staff, None)
    active = Appointment.status.in_(["booked", "confirmed"])
    return {
        "today_total": db.scalar(base.where(Appointment.start_time >= lo, Appointment.start_time < hi)),
        "today_active": db.scalar(base.where(Appointment.start_time >= lo, Appointment.start_time < hi, active)),
        "upcoming": db.scalar(base.where(Appointment.start_time >= datetime.now(IST), active)),
        "completed": db.scalar(base.where(Appointment.status == "completed")),
        "cancelled": db.scalar(base.where(Appointment.status == "cancelled")),
        "all_time": db.scalar(base),
    }


class StatusUpdate(BaseModel):
    status: Literal["confirmed", "completed", "cancelled"]
    cancellation_reason: str | None = Field(default=None, max_length=255)


NEXT = {"booked": {"confirmed", "completed", "cancelled"}, "confirmed": {"completed", "cancelled"}}


@router.patch("/{appointment_id}")
def update_status(appointment_id: Annotated[int, Path(gt=0)], data: StatusUpdate, staff: Staff, db: DB):
    a = db.scalar(select(Appointment).where(Appointment.id == appointment_id).with_for_update())
    if a is None or (staff["role"] == "doctor" and a.doctor_id != staff["doctor_id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if data.status not in NEXT.get(a.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {a.status} appointment cannot be marked {data.status}")
    if data.status == "completed" and _aware(a.start_time) > datetime.now(IST) + timedelta(minutes=15):
        raise HTTPException(status.HTTP_409_CONFLICT, "You can mark it completed once the appointment time has come")
    a.status = data.status
    if data.status == "cancelled":
        a.cancellation_reason = (data.cancellation_reason or f"Cancelled by {staff['role']}")[:255]
    db.commit()
    db.refresh(a)
    return _row(a, _patients({a.patient_auth_user_id})[a.patient_auth_user_id])
