"""Admin user management and internal user lookups."""
import hmac
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SERVICE_TO_SERVICE_TOKEN
from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Admin users"])


class UserRow(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class ActiveUpdate(BaseModel):
    is_active: bool


def require_service(x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None) -> None:
    if not x_service_token or not hmac.compare_digest(x_service_token, SERVICE_TO_SERVICE_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service credentials")


@router.get("/admin/users", response_model=list[UserRow])
def list_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    role: Literal["patient", "doctor", "admin"] | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where((User.email.ilike(like)) | (User.full_name.ilike(like)))
    return db.scalars(stmt.order_by(User.created_at.desc()).limit(500)).all()


@router.patch("/admin/users/{user_id}/active", response_model=UserRow)
def set_user_active(
    user_id: Annotated[int, Path(gt=0)],
    data: ActiveUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot block your own account")
    user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/internal/users", dependencies=[Depends(require_service)])
def users_by_ids(ids: Annotated[str, Query(max_length=4000)], db: Annotated[Session, Depends(get_db)]):
    """ids=1,2,3 -> [{id, full_name, email}] (used to show patient names to doctors)."""
    try:
        wanted = {int(x) for x in ids.split(",") if x.strip()}
    except ValueError:
        raise HTTPException(422, "ids must be comma-separated numbers")
    if not wanted:
        return []
    rows = db.scalars(select(User).where(User.id.in_(list(wanted)[:500]))).all()
    return [{"id": u.id, "full_name": u.full_name, "email": u.email} for u in rows]
