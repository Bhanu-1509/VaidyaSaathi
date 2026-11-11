"""Slot generation and capacity checks for home collection and centre visits."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import config
from app.models import LabBooking, LabCentre

TZ = ZoneInfo(config.TIMEZONE)
UTC = timezone.utc


def to_utc(dt: datetime) -> datetime:
    """Store and compare times in UTC so every database treats them the same."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def from_db(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _hm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def _window(collection_type: str, centre: LabCentre | None) -> tuple[time, time, int]:
    if collection_type == "home":
        return _hm(config.HOME_START), _hm(config.HOME_END), config.HOME_CAPACITY
    return _hm(centre.opens), _hm(centre.closes), config.CENTRE_CAPACITY


def _booked_counts(db: Session, collection_type: str, centre_id: int | None, day: date) -> dict[datetime, int]:
    start = to_utc(datetime.combine(day, time(0), TZ))
    q = (
        select(LabBooking.slot_start, func.count())
        .where(
            LabBooking.collection_type == collection_type,
            LabBooking.status != "cancelled",
            LabBooking.slot_start >= start,
            LabBooking.slot_start < start + timedelta(days=1),
        )
        .group_by(LabBooking.slot_start)
    )
    if collection_type == "centre":
        q = q.where(LabBooking.centre_id == centre_id)
    out = {}
    for slot, n in db.execute(q):
        out[from_db(slot).astimezone(TZ)] = n
    return out


def available_slots(
    db: Session, collection_type: str, centre: LabCentre | None, day: date
) -> list[tuple[datetime, int]]:
    now = datetime.now(TZ)
    if day < now.date() or day > now.date() + timedelta(days=config.BOOKING_DAYS_AHEAD):
        return []
    opens, closes, capacity = _window(collection_type, centre)
    earliest = now + timedelta(minutes=config.HOME_LEAD_MINUTES if collection_type == "home" else 30)
    booked = _booked_counts(db, collection_type, centre.id if centre else None, day)

    slots = []
    t = datetime.combine(day, opens, TZ)
    end = datetime.combine(day, closes, TZ)
    while t + timedelta(minutes=config.SLOT_MINUTES) <= end:
        if t >= earliest:
            slots.append((t, capacity - booked.get(t, 0)))
        t += timedelta(minutes=config.SLOT_MINUTES)
    return slots


def lock_slot(db: Session, collection_type: str, centre_id: int | None, slot: datetime) -> None:
    """Serialise bookings for one slot so two people can't take the last place at once."""
    if db.bind.dialect.name != "postgresql":
        return
    key = f"{collection_type}:{centre_id or 0}:{int(slot.timestamp())}"
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": key})
