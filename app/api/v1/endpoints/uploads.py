import time
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.crud import UploadSessionCRUD
from app.core.security import get_current_user
from app.core.exceptions import UploadSessionNotFound
from app.schemas import UploadSessionStatus, UploadSessionCompleted

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/{session_id}/status")
def get_upload_status(
    session_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get upload session status."""
    session = UploadSessionCRUD.get_session(db, session_id, current_user.id)
    if not session:
        raise UploadSessionNotFound(session_id)

    # Calculate elapsed time
    elapsed = int((datetime.utcnow() - session.created_at).total_seconds())

    if session.status == "completed":
        return UploadSessionCompleted(
            session_id=session.id,
            status=session.status,
            document_id=session.document_id,
            chunks_created=0,  # Would need to fetch from document
            completed_at=session.completed_at
        )
    elif session.status == "failed":
        return UploadSessionStatus(
            session_id=session.id,
            status=session.status,
            progress_percent=session.progress_percent,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=None,
            error=session.error_message
        )
    else:
        # Estimate remaining time
        estimated_remaining = None
        if session.progress_percent > 0:
            time_per_percent = elapsed / session.progress_percent
            estimated_remaining = int((100 - session.progress_percent) * time_per_percent)

        return UploadSessionStatus(
            session_id=session.id,
            status=session.status,
            progress_percent=session.progress_percent,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=estimated_remaining
        )


@router.get("")
def list_uploads(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List active uploads for current user."""
    # TODO: Implement query to list uploads
    return {"uploads": []}
