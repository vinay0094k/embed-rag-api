"""
Pytest configuration and fixtures for database isolation.
"""

import pytest
import tempfile
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.models import Base
from app.db.database import get_db
from main import app


@pytest.fixture(scope="function")
def test_db():
    """Create an in-memory SQLite database for testing."""
    # Use temporary file for test database
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = db_file.name
    db_file.close()

    # Create engine with test database
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    db = TestingSessionLocal()

    yield db

    # Cleanup
    db.close()
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client with isolated database."""
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app)

    # Clear overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client, test_db):
    """Register a test user and return auth headers."""
    from app.db.crud import UserCRUD, APIKeyCRUD

    # Create test user
    user = UserCRUD.create_user(test_db, "testuser", "test@example.com")

    # Generate API key
    api_key = APIKeyCRUD.create_api_key(test_db, user.id)

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
