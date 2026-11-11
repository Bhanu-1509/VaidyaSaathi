"""Read-only calls to the other VaidyaSaathi services."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import DOCTOR_SERVICE_URL, LAB_SERVICE_URL, SCHEDULING_SERVICE_URL, TIMEZONE

TZ = ZoneInfo(TIMEZONE)


class BackendError(Exception):
    pass


def _get(url: str, params: dict | None = None):
    try:
        r = httpx.get(url, params=params, timeout=10.0)
    except httpx.RequestError as exc:
        raise BackendError(f"Service not reachable: {url.split('/')[2]}") from exc
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise BackendError(f"Service returned {r.status_code}")
    return r.json()


def specialities() -> list[dict]:
    return _get(f"{DOCTOR_SERVICE_URL}/specializations/") or []


def doctors() -> list[dict]:
    return [d for d in (_get(f"{DOCTOR_SERVICE_URL}/doctors/") or []) if d.get("is_active", True)]


def doctor(doctor_id: int) -> dict | None:
    return _get(f"{DOCTOR_SERVICE_URL}/doctors/{doctor_id}")


def slots(doctor_id: int, day: date) -> list[datetime]:
    data = _get(
        f"{SCHEDULING_SERVICE_URL}/schedules/doctors/{doctor_id}/available-slots",
        {"requested_date": day.isoformat(), "duration_minutes": 30},
    )
    now = datetime.now(TZ)
    out = []
    for s in (data or {}).get("slots", []):
        t = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
        if t.tzinfo is None:  # scheduling-service returns India local time without an offset
            t = t.replace(tzinfo=TZ)
        if t > now:
            out.append(t.astimezone(TZ))
    return out


def next_days(n: int) -> list[date]:
    today = datetime.now(TZ).date()
    return [today + timedelta(days=i) for i in range(n)]


def lab_tests(q: str | None = None, category: str | None = None) -> list[dict]:
    params = {k: v for k, v in {"q": q, "category": category}.items() if v}
    return _get(f"{LAB_SERVICE_URL}/lab/tests", params) or []


def lab_categories() -> list[dict]:
    return _get(f"{LAB_SERVICE_URL}/lab/categories") or []
