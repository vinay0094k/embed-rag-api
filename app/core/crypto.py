"""Cryptographic utilities for API key hashing."""

import hashlib
import hmac
from app.core.config import settings


def hash_api_key(api_key: str) -> str:
    """Hash an API key using HMAC-SHA256.

    Uses SECRET_KEY for additional security beyond simple hashing.
    """
    return hashlib.sha256(
        (api_key + settings.SECRET_KEY).encode()
    ).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify that a plain API key matches the stored hash."""
    return hmac.compare_digest(hash_api_key(plain_key), hashed_key)
