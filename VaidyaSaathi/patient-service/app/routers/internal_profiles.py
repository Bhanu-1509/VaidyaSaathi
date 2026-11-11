"""Internal lookup of patient contact details (used by appointment-service for doctors and admins)."""
import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient

router = APIRouter(prefix="/patients/internal", tags=["Internal"], include_in_schema=False)


def require_service(x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None) -> None:
    expected = os.getenv("SERVICE_TO_SERVICE_TOKEN")
    if not expected or not x_service_token or not hmac.compare_digest(x_service_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service credentials")


@router.get("/profiles", dependencies=[Depends(require_service)])
def profiles(ids: Annotated[str, Query(max_length=4000)], db: Annotated[Session, Depends(get_db)]):
    try:
        wanted = [int(x) for x in ids.split(",") if x.strip()][:500]
    except ValueError:
        raise HTTPException(422, "ids must be comma-separated numbers")
    rows = db.query(Patient).filter(Patient.auth_user_id.in_(wanted)).all() if wanted else []
    return [
        {
            "auth_user_id": p.auth_user_id,
            "phone_number": p.phone_number,
            "gender": p.gender,
            "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
            "address": p.address,
        }
        for p in rows
    ]
