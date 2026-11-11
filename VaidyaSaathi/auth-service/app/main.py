from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.models.email_otp import EmailOtp  # noqa: F401  (creates the table)
from app.models.user import User
from app.routers.admin_users import router as admin_users_router
from app.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register the User model and create missing tables.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="VaidyaSaathi Auth Service",
    version="1.0.0",
    description="Authentication and user identity management",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(admin_users_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
