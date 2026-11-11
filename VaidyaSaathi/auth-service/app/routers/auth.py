import hmac
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import jwt
from app.core.dependencies import require_admin
from app.models.user import User
from app.database import get_db
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    DoctorAccountCreate,
    OtpRequest,
    OtpVerify,
    RegisterComplete,
    RegistrationTokenResponse,
)
from app.core.config import SERVICE_TO_SERVICE_TOKEN, SHOW_DEV_OTP
from app.services.otp_service import (
    OTP_TTL_SECONDS,
    RESEND_SECONDS,
    OtpError,
    decode_registration_token,
    request_otp,
    verify_otp,
)
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_tokens,
    refresh_tokens,
    create_doctor_account,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/register/request-otp", status_code=status.HTTP_202_ACCEPTED)
def request_registration_otp(
    data: OtpRequest,
    db: Session = Depends(get_db),
):
    """Step 1: email a 6-digit code to the address being registered."""
    try:
        delivery, code = request_otp(db, str(data.email), data.full_name)
    except OtpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    result = {
        "detail": "Verification code sent",
        "delivery": "email" if delivery == "sent" else "console",
        "resend_after": RESEND_SECONDS,
        "expires_in": OTP_TTL_SECONDS,
    }
    # Email is not configured: the code was only printed in the notification-service log.
    if delivery != "sent" and SHOW_DEV_OTP:
        result["dev_code"] = code
    return result


@router.post("/register/verify-otp", response_model=RegistrationTokenResponse)
def verify_registration_otp(
    data: OtpVerify,
    db: Session = Depends(get_db),
):
    """Step 2: check the code and return a short-lived registration token."""
    try:
        return {"registration_token": verify_otp(db, str(data.email), data.otp)}
    except OtpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/register/complete",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def complete_registration(
    data: RegisterComplete,
    db: Session = Depends(get_db),
):
    """Step 3: set the password. Only possible with a verified-email token."""
    try:
        email = decode_registration_token(data.registration_token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email verification expired. Please start again.",
        ) from exc
    try:
        return register_user(
            db,
            RegisterRequest(full_name=data.full_name, email=email, password=data.password),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    try:
        user = authenticate_user(db, data)
        return create_tokens(user)
    except ValueError as exc:
        message = str(exc)

        if message == "Account is inactive":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
def refresh(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        return refresh_tokens(db, data)
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc


@router.post(
    "/admin/doctors",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_doctor(
    data: DoctorAccountCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        return create_doctor_account(
            db=db,
            full_name=data.full_name,
            email=str(data.email),
            password=data.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

@router.get("/internal/doctor-accounts/{user_id}")
def verify_doctor_account(
    user_id: int,
    x_service_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Authenticate the calling service.
    if (
        not SERVICE_TO_SERVICE_TOKEN
        or not x_service_token
        or not hmac.compare_digest(
            x_service_token,
            SERVICE_TO_SERVICE_TOKEN,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials",
        )

    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account does not have the doctor role",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor account is inactive",
        )

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }

@router.get("/internal/users/{user_id}/status")
def get_internal_user_status(
    user_id: int,
    x_service_token: str | None = Header(
        default=None,
        alias="X-Service-Token",
    ),
    db: Session = Depends(get_db),
):
    if (
        not SERVICE_TO_SERVICE_TOKEN
        or not x_service_token
        or not hmac.compare_digest(
            x_service_token,
            SERVICE_TO_SERVICE_TOKEN,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials",
        )

    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return {
        "id": user.id,
        "role": user.role,
        "is_active": user.is_active,
    }