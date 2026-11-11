"""Create an admin account.

Docker:  docker compose exec auth-service python -m app.create_admin
Local:   python -m app.create_admin   (run inside auth-service/)
"""
import getpass
import sys

from pydantic import TypeAdapter, EmailStr, ValidationError

from app.database import Base, SessionLocal, engine
from app.models import email_otp  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.auth_service import create_admin_account


def main() -> None:
    Base.metadata.create_all(bind=engine)

    full_name = input("Full name: ").strip()
    if len(full_name) < 2:
        sys.exit("Name must be at least 2 characters.")

    try:
        email = TypeAdapter(EmailStr).validate_python(input("Email: ").strip())
    except ValidationError:
        sys.exit("That is not a valid email address.")

    password = getpass.getpass("Password (min 12 characters): ")
    if len(password) < 12:
        sys.exit("Password must be at least 12 characters.")
    if getpass.getpass("Confirm password: ") != password:
        sys.exit("Passwords do not match.")

    db = SessionLocal()
    try:
        user = create_admin_account(db, full_name, str(email), password)
    except ValueError as exc:
        sys.exit(str(exc))
    finally:
        db.close()
    print(f"Admin created: {user.email} (user ID {user.id})")


if __name__ == "__main__":
    main()
