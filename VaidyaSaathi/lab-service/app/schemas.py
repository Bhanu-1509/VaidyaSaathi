from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

BookingStatus = Literal["booked", "sample_collected", "processing", "report_ready", "cancelled"]


class TestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    also_known_as: str | None
    category: str
    sample_type: str
    fasting_hours: int
    report_hours: int
    price: Decimal
    mrp: Decimal
    description: str
    preparation: str
    parameters: list[str]
    is_package: bool
    included_codes: list[str]
    is_popular: bool


class TestAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    also_known_as: str | None
    category: str
    sample_type: str
    fasting_hours: int
    report_hours: int
    price: Decimal
    mrp: Decimal
    description: str
    preparation: str
    parameters: list[str]
    is_package: bool
    included_codes: list[str]
    is_popular: bool
    is_active: bool


class TestCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_]{2,40}$", description="Short unique code, e.g. VIT_D")
    name: str = Field(min_length=2, max_length=160)
    also_known_as: str | None = Field(default=None, max_length=200)
    category: str = Field(min_length=2, max_length=60)
    sample_type: str = Field(default="Blood", min_length=2, max_length=40)
    fasting_hours: int = Field(default=0, ge=0, le=24)
    report_hours: int = Field(default=24, ge=1, le=720)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    mrp: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    description: str = Field(default="", max_length=2000)
    preparation: str = Field(default="", max_length=1000)
    parameters: list[str] = Field(default_factory=list, max_length=100)
    is_package: bool = False
    included_codes: list[str] = Field(default_factory=list, max_length=60)
    is_popular: bool = False

    @model_validator(mode="after")
    def check(self):
        if self.price > self.mrp:
            raise ValueError("Price cannot be more than MRP")
        if self.is_package and len(self.included_codes) < 2:
            raise ValueError("A package must include at least 2 tests")
        return self


class TestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    also_known_as: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    sample_type: str | None = Field(default=None, min_length=2, max_length=40)
    fasting_hours: int | None = Field(default=None, ge=0, le=24)
    report_hours: int | None = Field(default=None, ge=1, le=720)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    mrp: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    description: str | None = Field(default=None, max_length=2000)
    preparation: str | None = Field(default=None, max_length=1000)
    parameters: list[str] | None = Field(default=None, max_length=100)
    included_codes: list[str] | None = Field(default=None, max_length=60)
    is_popular: bool | None = None
    is_active: bool | None = None


class CentreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    address: str | None = Field(default=None, min_length=5, max_length=300)
    city: str | None = Field(default=None, min_length=2, max_length=80)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    phone: str | None = Field(default=None, max_length=20)
    opens: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    closes: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    is_active: bool | None = None


class CentreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    city: str
    pincode: str
    phone: str | None
    opens: str
    closes: str
    is_active: bool = True


class CentreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    address: str = Field(min_length=5, max_length=300)
    city: str = Field(min_length=2, max_length=80)
    pincode: str = Field(pattern=r"^\d{6}$")
    phone: str | None = Field(default=None, max_length=20)
    opens: str = Field(default="07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    closes: str = Field(default="19:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def check_hours(self):
        if self.opens >= self.closes:
            raise ValueError("Opening time must be before closing time")
        return self


class SlotOut(BaseModel):
    start_time: datetime
    remaining: int


class BookingCreate(BaseModel):
    test_ids: list[int] = Field(min_length=1, max_length=30)
    collection_type: Literal["home", "centre"]
    centre_id: int | None = Field(default=None, gt=0)
    patient_name: str = Field(min_length=2, max_length=150)
    contact_phone: str = Field(pattern=r"^\+?[0-9 ]{7,20}$")
    address: str | None = Field(default=None, max_length=500)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    slot_start: datetime

    @model_validator(mode="after")
    def check(self):
        if self.slot_start.tzinfo is None:
            raise ValueError("slot_start must include a timezone")
        if self.collection_type == "home":
            if not self.address or len(self.address.strip()) < 10:
                raise ValueError("Enter the full address for home collection")
            if not self.pincode:
                raise ValueError("Enter the pincode for home collection")
        elif not self.centre_id:
            raise ValueError("Choose a lab centre")
        return self


class BookingCancel(BaseModel):
    cancellation_reason: str | None = Field(default=None, max_length=255)


class BookingAdminUpdate(BaseModel):
    status: BookingStatus | None = None
    report_url: HttpUrl | None = None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_auth_user_id: int
    collection_type: str
    centre: CentreOut | None
    patient_name: str
    contact_phone: str
    address: str | None
    pincode: str | None
    slot_start: datetime
    status: BookingStatus
    items: list[dict]
    subtotal: Decimal
    collection_fee: Decimal
    total: Decimal
    report_url: str | None
    cancellation_reason: str | None
    created_at: datetime

    @field_validator("slot_start", "created_at")
    @classmethod
    def assume_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
