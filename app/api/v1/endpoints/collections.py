from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.crud import CollectionCRUD
from app.db.models import Collection
from app.core.security import get_current_user
from app.core.exceptions import CollectionNotFound
from app.schemas import (
    CollectionCreate, CollectionResponse, CollectionListResponse, CollectionUpdate,
    CollectionStatsResponse
)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("", response_model=CollectionResponse)
def create_collection(
    collection_data: CollectionCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new collection."""
    collection = CollectionCRUD.create_collection(
        db,
        current_user.id,
        collection_data.name,
        collection_data.description
    )
    return collection


@router.get("", response_model=CollectionListResponse)
def list_collections(
    offset: int = 0,
    limit: int = 50,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all collections for the current user with pagination."""
    if offset < 0 or limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset must be >= 0, limit must be 1-1000"
        )

    # Get total count
    total = db.query(Collection).filter(Collection.user_id == current_user.id).count()

    # Get paginated results
    collections = db.query(Collection).filter(
        Collection.user_id == current_user.id
    ).order_by(Collection.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "collections": collections,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/{collection_id}", response_model=CollectionResponse)
def get_collection(
    collection_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get collection details."""
    collection = CollectionCRUD.get_collection(db, collection_id, current_user.id)
    if not collection:
        raise CollectionNotFound(collection_id)
    return collection


@router.put("/{collection_id}", response_model=CollectionResponse)
def update_collection(
    collection_id: str,
    collection_data: CollectionUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update collection name and/or description."""
    collection = CollectionCRUD.get_collection(db, collection_id, current_user.id)
    if not collection:
        raise CollectionNotFound(collection_id)

    updated_collection = CollectionCRUD.update_collection(
        db, collection_id, current_user.id,
        name=collection_data.name,
        description=collection_data.description
    )
    return updated_collection


@router.get("/{collection_id}/stats", response_model=CollectionStatsResponse)
def get_collection_stats(
    collection_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get collection statistics."""
    collection = CollectionCRUD.get_collection(db, collection_id, current_user.id)
    if not collection:
        raise CollectionNotFound(collection_id)

    stats = CollectionCRUD.get_collection_stats(db, collection_id, current_user.id)
    return CollectionStatsResponse(**stats)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a collection."""
    collection = CollectionCRUD.get_collection(db, collection_id, current_user.id)
    if not collection:
        raise CollectionNotFound(collection_id)

    # Delete from vector store and BM25 index
    from app.services.rag_service import get_rag_service
    rag_service = get_rag_service()
    rag_service.delete_collection(collection_id)

    # Delete from database (cascades to documents and chunks)
    CollectionCRUD.delete_collection(db, collection_id, current_user.id)
    return None
