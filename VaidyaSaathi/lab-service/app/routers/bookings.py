from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.auth import require_patient
from app.database import get_db
from app.models import LabBooking, LabCentre, LabTest
from app.schemas import BookingCancel, BookingCreate, BookingOut
from app.slots import TZ, available_slots, from_db, lock_slot, to_utc

router = APIRouter(prefix="/lab/bookings", tags=["Lab bookings"])


def collection_fee(collection_type: str, subtotal: Decimal) -> Decimal:
    if collection_type == "home" and subtotal < config.FREE_COLLECTION_ABOVE:
        return Decimal(config.HOME_COLLECTION_FEE)
    return Decimal(0)


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    data: BookingCreate,
    patient: Annotated[dict, Depends(require_patient)],
    db: Annotated[Session, Depends(get_db)],
):
    ids = list(dict.fromkeys(data.test_ids))  # drop duplicates, keep order
    tests = db.scalars(select(LabTest).where(LabTest.id.in_(ids), LabTest.is_active.is_(True))).all()
    if len(tests) != len(ids):
        raise HTTPException(422, "One or more tests are no longer available")

    centre = None
    if data.collection_type == "centre":
        centre = db.get(LabCentre, data.centre_id)
        if centre is None or not centre.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab centre not found")

    slot = data.slot_start.astimezone(TZ).replace(second=0, microsecond=0)
    lock_slot(db, data.collection_type, centre.id if centre else None, slot)
    open_slots = dict(available_slots(db, data.collection_type, centre, slot.date()))
    if slot not in open_slots:
        raise HTTPException(status.HTTP_409_CONFLICT, "This time slot is not available. Please pick another.")
    if open_slots[slot] <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot just filled up. Please pick another.")

    order = {tid: i for i, tid in enumerate(ids)}
    tests = sorted(tests, key=lambda t: order[t.id])
    subtotal = sum((Decimal(t.price) for t in tests), Decimal(0))
    fee = collection_fee(data.collection_type, subtotal)
    booking = LabBooking(
        patient_auth_user_id=patient["user_id"],
        collection_type=data.collection_type,
        centre_id=centre.id if centre else None,
        patient_name=data.patient_name.strip(),
        contact_phone=data.contact_phone.strip(),
        address=data.address.strip() if data.collection_type == "home" else None,
        pincode=data.pincode if data.collection_type == "home" else None,
        slot_start=to_utc(slot),
        status="booked",
        items=[{"id": t.id, "code": t.code, "name": t.name, "price": str(t.price),
                "fasting_hours": t.fasting_hours, "is_package": t.is_package} for t in tests],
        subtotal=subtotal,
        collection_fee=fee,
        total=subtotal + fee,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/me", response_model=list[BookingOut])
def my_bookings(
    patient: Annotated[dict, Depends(require_patient)],
    db: Annotated[Session, Depends(get_db)],
):
    return db.scalars(
        select(LabBooking)
        .where(LabBooking.patient_auth_user_id == patient["user_id"])
        .order_by(LabBooking.slot_start.desc())
    ).all()


@router.patch("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: Annotated[int, Path(gt=0)],
    data: BookingCancel,
    patient: Annotated[dict, Depends(require_patient)],
    db: Annotated[Session, Depends(get_db)],
):
    booking = db.get(LabBooking, booking_id)
    if booking is None or booking.patient_auth_user_id != patient["user_id"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status != "booked":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only bookings that have not started can be cancelled")
    if from_db(booking.slot_start) <= datetime.now(TZ):
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot has already started")
    booking.status = "cancelled"
    booking.cancellation_reason = data.cancellation_reason
    db.commit()
    db.refresh(booking)
    return booking
