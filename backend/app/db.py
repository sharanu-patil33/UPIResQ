import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./upi.db")

# check_same_thread=False: several threads will touch the database later.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        # SQLite ignores foreign keys unless you switch this on for every connection.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def init_db():
    """Create every table. Safe to call more than once."""
    from app import models  # noqa: F401  (importing registers the tables)
    Base.metadata.create_all(bind=engine)
