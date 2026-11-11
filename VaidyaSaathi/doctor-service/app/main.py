
from fastapi import FastAPI

from app.database import Base, engine

# Import models so SQLAlchemy registers their tables
from app.models import doctors
from app.models import doctor_availability
from app.models import doctor_leave
from app.models import doctor_specialization  # registers the specializations table

# Import routers
from app.routers.doctors import router as doctors_router
from app.routers.specializations import router as specializations_router
from app.routers.doctor_availability import router as availability_router
from app.routers.doctor_leave import router as leave_router
from app.routers.internal import router as internal_router


# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="VidyaSaathi Doctor Service")


# Register routers
app.include_router(doctors_router)
app.include_router(specializations_router)
app.include_router(availability_router)
app.include_router(leave_router)
app.include_router(internal_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "doctor-service"}
