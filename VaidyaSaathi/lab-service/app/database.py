import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import LAB_DATABASE_URL

log = logging.getLogger("lab")


def ensure_database_exists() -> None:
    """Create the Postgres database on first start.

    Postgres runs docker/init-db.sql only when its volume is new, so an existing
    setup would otherwise have no lab_db.
    """
    url = make_url(LAB_DATABASE_URL)
    if not url.drivername.startswith("postgresql") or not url.database:
        return
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database})
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
                log.info("Created database %s", url.database)
    finally:
        admin.dispose()


engine = create_engine(LAB_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
