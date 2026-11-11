
from fastapi import FastAPI

from app.database import Base, engine
from app.models.patient import Patient
from app.routers.patients import router as patients_router
from app.routers.internal_profiles import router as internal_profiles_router


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="VidyaSaathi Patient Service",
    description="Patient profile management APIs",
    version="1.0.0",
)

app.include_router(internal_profiles_router)
app.include_router(patients_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "patient-service",
    }
