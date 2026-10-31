"""Runs before any test: use a throwaway database and create all tables."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_upi.db"
if os.path.exists("test_upi.db"):
    os.remove("test_upi.db")

from app.db import init_db  # noqa: E402  (must come after the environment variable)

init_db()
