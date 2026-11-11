from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LabTest(Base):
    """A single test or a health package (is_package=True)."""

    __tablename__ = "lab_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    also_known_as: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    sample_type: Mapped[str] = mapped_column(String(40), nullable=False, default="Blood")
    fasting_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    mrp: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    preparation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_package: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    included_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_popular: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LabCentre(Base):
    __tablename__ = "lab_centres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    opens: Mapped[str] = mapped_column(String(5), nullable=False, default="07:00")
    closes: Mapped[str] = mapped_column(String(5), nullable=False, default="19:00")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LabBooking(Base):
    __tablename__ = "lab_bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_auth_user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    collection_type: Mapped[str] = mapped_column(String(10), nullable=False)  # home | centre
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("lab_centres.id"))
    patient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    pincode: Mapped[str | None] = mapped_column(String(10))
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    # booked -> sample_collected -> processing -> report_ready ; or cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked")
    items: Mapped[list] = mapped_column(JSON, nullable=False)  # snapshot: [{id, code, name, price}]
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    collection_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    report_url: Mapped[str | None] = mapped_column(String(500))
    cancellation_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    centre: Mapped[LabCentre | None] = relationship()
