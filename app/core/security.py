import secrets
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.db.database import get_db
from app.db.models import User


def generate_api_key() -> str:
    """Generate a new API key."""
    return f"{settings.API_KEY_PREFIX}{secrets.token_urlsafe(settings.API_KEY_LENGTH)}"


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate API key from Authorization header.

    Verifies key hash (not plain text) for security.
    """
    if not authorization:
        raise UnauthorizedError()

    try:
        scheme, credentials = authorization.split()
        if scheme.lower() != "bearer":
            raise UnauthorizedError()
    except ValueError:
        raise UnauthorizedError()

    # Import here to avoid circular imports
    from app.db.crud import APIKeyCRUD

    # Use CRUD method to verify hash
    api_key_record = APIKeyCRUD.get_api_key(db, credentials)

    if not api_key_record:
        raise UnauthorizedError()

    # Verify user is active
    user = db.query(User).filter(User.id == api_key_record.user_id).first()
    if not user or not user.active:
        raise UnauthorizedError()

    return user
