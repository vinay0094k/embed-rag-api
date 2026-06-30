from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.crud import UserCRUD, APIKeyCRUD
from app.core.security import get_current_user
from app.schemas import UserRegister, UserResponse, APIKeyResponse, APIKeyListResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user."""
    existing_user = UserCRUD.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    user = UserCRUD.create_user(db, user_data.username, user_data.email)
    return user


@router.post("/generate-key", response_model=APIKeyResponse)
def generate_api_key(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a new API key for the current user."""
    api_key = APIKeyCRUD.create_api_key(db, current_user.id)
    return {"api_key": api_key}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user = Depends(get_current_user)):
    """Get current authenticated user info."""
    return current_user


@router.get("/keys", response_model=APIKeyListResponse)
def list_api_keys(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all API keys for the current user."""
    keys = APIKeyCRUD.list_user_api_keys(db, current_user.id)
    return {
        "keys": keys,
        "total": len(keys)
    }


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke an API key."""
    success = APIKeyCRUD.revoke_api_key(db, key_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return None
