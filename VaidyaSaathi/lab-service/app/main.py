from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers the tables)
from app.database import Base, SessionLocal, engine, ensure_database_exists
from app.routers import admin, bookings, catalogue
from app.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_database_exists()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="VaidyaSaathi Lab Service", version="1.0.0", lifespan=lifespan)
app.include_router(catalogue.router)
app.include_router(bookings.router)
app.include_router(admin.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "service": "lab-service"}
