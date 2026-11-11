
from fastapi import FastAPI
from sqlalchemy import text

from app.database import Base, engine

# Import every model before create_all().
from app.models.appointment import Appointment
from app.models.doctor_schedule_lock import DoctorScheduleLock

from app.routers.appointments import router as appointments_router
from app.routers.staff import router as staff_router


# PostgreSQL extension required by the appointment overlap constraint.
with engine.begin() as connection:
    connection.execute(
        text("CREATE EXTENSION IF NOT EXISTS btree_gist")
    )

# Create the database tables.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="VidyaSaathi Appointment Service",
    description="Appointment booking, cancellation, and scheduling coordination",
    version="1.0.0",
)

app.include_router(staff_router)
app.include_router(appointments_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "appointment-service",
    }
