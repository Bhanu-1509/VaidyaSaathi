from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.doctor_specialization import Specialization
from app.schemas import SpecializationResponse
from app.routers.doctors import require_admin


class SpecializationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)

router = APIRouter(
    prefix="/specializations",
    tags=["Specializations"],
)


@router.get("/", response_model=list[SpecializationResponse])
def get_specializations(db: Session = Depends(get_db)):
    return (
        db.query(Specialization)
        .order_by(Specialization.name)
        .all()
    )


@router.post("/", response_model=SpecializationResponse, status_code=status.HTTP_201_CREATED)
def create_specialization(
    data: SpecializationCreate,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    name = " ".join(data.name.split())
    exists = db.query(Specialization).filter(Specialization.name.ilike(name)).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This speciality already exists")
    spec = Specialization(name=name)
    db.add(spec)
    db.commit()
    db.refresh(spec)
    return spec
