from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LabCentre, LabTest
from app.schemas import CentreOut, SlotOut, TestOut
from app.slots import available_slots

router = APIRouter(prefix="/lab", tags=["Lab catalogue"])


@router.get("/categories")
def list_categories(db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(LabTest.category, func.count())
        .where(LabTest.is_active.is_(True))
        .group_by(LabTest.category)
        .order_by(LabTest.category)
    )
    return [{"name": name, "count": n} for name, n in rows]


@router.get("/tests", response_model=list[TestOut])
def list_tests(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=80)] = None,
    category: Annotated[str | None, Query(max_length=60)] = None,
    kind: Literal["all", "tests", "packages"] = "all",
    popular: bool = False,
):
    stmt = select(LabTest).where(LabTest.is_active.is_(True))
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(LabTest.name).like(like),
                func.lower(func.coalesce(LabTest.also_known_as, "")).like(like),
                func.lower(LabTest.code).like(like),
                func.lower(LabTest.category).like(like),
            )
        )
    if category:
        stmt = stmt.where(LabTest.category == category)
    if kind != "all":
        stmt = stmt.where(LabTest.is_package.is_(kind == "packages"))
    if popular:
        stmt = stmt.where(LabTest.is_popular.is_(True))
    return db.scalars(stmt.order_by(LabTest.is_package.desc(), LabTest.is_popular.desc(), LabTest.name)).all()


@router.get("/tests/{test_id}", response_model=TestOut)
def get_test(test_id: int, db: Annotated[Session, Depends(get_db)]):
    test = db.get(LabTest, test_id)
    if test is None or not test.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")
    return test


@router.get("/centres", response_model=list[CentreOut])
def list_centres(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(LabCentre).where(LabCentre.is_active.is_(True)).order_by(LabCentre.name)).all()


@router.get("/slots", response_model=list[SlotOut])
def list_slots(
    db: Annotated[Session, Depends(get_db)],
    collection_type: Literal["home", "centre"],
    requested_date: date,
    centre_id: Annotated[int | None, Query(gt=0)] = None,
):
    centre = None
    if collection_type == "centre":
        centre = db.get(LabCentre, centre_id) if centre_id else None
        if centre is None or not centre.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab centre not found")
    return [
        {"start_time": t, "remaining": n}
        for t, n in available_slots(db, collection_type, centre, requested_date)
    ]
