"""Unit tests must never use a developer's production database credentials."""
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@127.0.0.1:5432/nortverse_test"
os.environ["DATABASE_URL_SYNC"] = ""
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
