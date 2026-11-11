from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import LabBooking, LabCentre, LabTest
from app.schemas import (
    BookingAdminUpdate, BookingOut, BookingStatus, CentreCreate, CentreOut, CentreUpdate,
    TestAdminOut, TestCreate, TestUpdate,
)
from app.slots import TZ, to_utc

router = APIRouter(prefix="/lab/admin", tags=["Lab admin"])

# Allowed status moves. Admins can also attach a report at any non-cancelled stage.
NEXT = {
    "booked": {"sample_collected", "cancelled"},
    "sample_collected": {"processing", "report_ready"},
    "processing": {"report_ready"},
    "report_ready": set(),
    "cancelled": set(),
}


@router.get("/bookings", response_model=list[BookingOut])
def all_bookings(
    _: Annotated[dict, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[BookingStatus | None, Query(alias="status")] = None,
    on_date: Annotated[date | None, Query(alias="date")] = None,
):
    stmt = select(LabBooking)
    if status_filter:
        stmt = stmt.where(LabBooking.status == status_filter)
    if on_date:
        start = to_utc(datetime.combine(on_date, time(0), TZ))
        stmt = stmt.where(LabBooking.slot_start >= start, LabBooking.slot_start < start + timedelta(days=1))
    return db.scalars(stmt.order_by(LabBooking.slot_start.desc()).limit(300)).all()


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
def update_booking(
    booking_id: Annotated[int, Path(gt=0)],
    data: BookingAdminUpdate,
    _: Annotated[dict, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    booking = db.get(LabBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if data.status and data.status != booking.status:
        if data.status not in NEXT[booking.status]:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Cannot move a booking from {booking.status} to {data.status}"
            )
        booking.status = data.status
    if data.report_url is not None:
        if booking.status == "cancelled":
            raise HTTPException(status.HTTP_409_CONFLICT, "Cannot add a report to a cancelled booking")
        booking.report_url = str(data.report_url)
        booking.status = "report_ready"
    if booking.status == "report_ready" and not booking.report_url:
        raise HTTPException(422, "Add the report link to mark it ready")
    db.commit()
    db.refresh(booking)
    return booking


@router.post("/centres", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
def add_centre(
    data: CentreCreate,
    _: Annotated[dict, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    centre = LabCentre(**data.model_dump())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.patch("/centres/{centre_id}/deactivate", response_model=CentreOut)
def deactivate_centre(
    centre_id: Annotated[int, Path(gt=0)],
    _: Annotated[dict, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    centre = db.get(LabCentre, centre_id)
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab centre not found")
    centre.is_active = False
    db.commit()
    db.refresh(centre)
    return centre


# ---------------- Centres: list all and edit ----------------
@router.get("/centres", response_model=list[CentreOut])
def all_centres(_: Annotated[dict, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(LabCentre).order_by(LabCentre.is_active.desc(), LabCentre.name)).all()


@router.patch("/centres/{centre_id}", response_model=CentreOut)
def edit_centre(
    centre_id: Annotated[int, Path(gt=0)],
    data: CentreUpdate,
    _: Annotated[dict, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    centre = db.get(LabCentre, centre_id)
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab centre not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(centre, k, v)
    if centre.opens >= centre.closes:
        raise HTTPException(422, "Opening time must be before closing time")
    db.commit()
    db.refresh(centre)
    return centre


# ---------------- Tests and packages ----------------
def _package_fields(db: Session, codes: list[str]) -> list[str]:
    codes = [c.strip().upper() for c in codes if c.strip()]
    found = {t.code: t for t in db.scalars(select(LabTest).where(LabTest.code.in_(codes), LabTest.is_package.is_(False)))}
    missing = [c for c in codes if c not in found]
    if missing:
        raise HTTPException(422, f"Unknown test codes: {', '.join(missing)}")
    return [found[c].name for c in codes]


@router.get("/tests", response_model=list[TestAdminOut])
def all_tests(_: Annotated[dict, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(LabTest).order_by(LabTest.is_package.desc(), LabTest.category, LabTest.name)).all()


@router.post("/tests", response_model=TestAdminOut, status_code=status.HTTP_201_CREATED)
def add_test(data: TestCreate, _: Annotated[dict, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]):
    if db.scalar(select(LabTest.id).where(LabTest.code == data.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A test with this code already exists")
    values = data.model_dump()
    if data.is_package:
        values["included_codes"] = [c.strip().upper() for c in data.included_codes]
        values["parameters"] = _package_fields(db, values["included_codes"])
        values["also_known_as"] = values["also_known_as"] or f"{len(values['included_codes'])} tests"
    else:
        values["included_codes"] = []
    test = LabTest(**values)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.patch("/tests/{test_id}", response_model=TestAdminOut)
def edit_test(
    test_id: Annotated[int, Path(gt=0)],
    data: TestUpdate,
    _: Annotated[dict, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    test = db.get(LabTest, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")
    changes = data.model_dump(exclude_unset=True)
    if "included_codes" in changes:
        if not test.is_package:
            raise HTTPException(422, "Only packages include other tests")
        changes["included_codes"] = [c.strip().upper() for c in changes["included_codes"]]
        if len(changes["included_codes"]) < 2:
            raise HTTPException(422, "A package must include at least 2 tests")
        changes["parameters"] = _package_fields(db, changes["included_codes"])
    for k, v in changes.items():
        setattr(test, k, v)
    if Decimal(test.price) > Decimal(test.mrp):
        raise HTTPException(422, "Price cannot be more than MRP")
    db.commit()
    db.refresh(test)
    return test


# ---------------- Dashboard numbers ----------------
@router.get("/stats")
def lab_stats(_: Annotated[dict, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]):
    now = datetime.now(TZ)
    day0 = to_utc(datetime.combine(now.date(), time(0), TZ))
    month0 = to_utc(datetime.combine(now.date().replace(day=1), time(0), TZ))
    by_status = dict(db.execute(select(LabBooking.status, func.count()).group_by(LabBooking.status)).all())
    live = LabBooking.status != "cancelled"
    return {
        "today": db.scalar(select(func.count()).where(LabBooking.slot_start >= day0,
                                                      LabBooking.slot_start < day0 + timedelta(days=1), live)),
        "awaiting_collection": by_status.get("booked", 0),
        "in_lab": by_status.get("sample_collected", 0) + by_status.get("processing", 0),
        "reports_ready": by_status.get("report_ready", 0),
        "cancelled": by_status.get("cancelled", 0),
        "revenue_this_month": float(db.scalar(select(func.coalesce(func.sum(LabBooking.total), 0))
                                              .where(LabBooking.created_at >= month0, live)) or 0),
        "active_tests": db.scalar(select(func.count()).select_from(LabTest).where(LabTest.is_active.is_(True), LabTest.is_package.is_(False))),
        "active_packages": db.scalar(select(func.count()).select_from(LabTest).where(LabTest.is_active.is_(True), LabTest.is_package.is_(True))),
        "centres": db.scalar(select(func.count()).select_from(LabCentre).where(LabCentre.is_active.is_(True))),
    }
