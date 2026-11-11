"""Service-to-service routes used by scheduling-service.

scheduling-service reads a doctor's weekly hours and leave from
/doctors/internal/{id}/availability and /doctors/internal/{id}/leaves,
authenticated with the shared X-Service-Token instead of a user token.
"""
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.config import SERVICE_TO_SERVICE_TOKEN
from app.database import get_db
from app.models.doctor_availability import DoctorAvailability
from app.models.doctor_leave import DoctorLeave
from app.models.doctors import Doctor
from app.schemas.doctor_availability import DoctorAvailabilityResponse
from app.schemas.doctor_leave import DoctorLeaveResponse

router = APIRouter(prefix="/doctors/internal", tags=["Internal"])


def require_service(x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None) -> None:
    if not SERVICE_TO_SERVICE_TOKEN or not x_service_token or not hmac.compare_digest(
        x_service_token, SERVICE_TO_SERVICE_TOKEN
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service credentials")


def _doctor(db: Session, doctor_id: int) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    return doctor


@router.get("/{doctor_id}/availability", response_model=list[DoctorAvailabilityResponse],
            dependencies=[Depends(require_service)])
def internal_availability(doctor_id: Annotated[int, Path(gt=0)], db: Session = Depends(get_db)):
    _doctor(db, doctor_id)
    return (
        db.query(DoctorAvailability)
        .filter(DoctorAvailability.doctor_id == doctor_id)
        .order_by(DoctorAvailability.day_of_week)
        .all()
    )


@router.get("/{doctor_id}/leaves", response_model=list[DoctorLeaveResponse],
            dependencies=[Depends(require_service)])
def internal_leaves(doctor_id: Annotated[int, Path(gt=0)], db: Session = Depends(get_db)):
    _doctor(db, doctor_id)
    return (
        db.query(DoctorLeave)
        .filter(DoctorLeave.doctor_id == doctor_id)
        .order_by(DoctorLeave.start_date)
        .all()
    )
