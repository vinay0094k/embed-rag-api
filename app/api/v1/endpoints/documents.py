from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from sqlalchemy.orm import Session
import logging

from app.db.database import get_db
from app.db.crud import DocumentCRUD, CollectionCRUD, UploadSessionCRUD, ChunkCRUD
from app.db.models import DocumentStatus, Chunk, Document
from app.core.security import get_current_user
from app.core.exceptions import CollectionNotFound, DocumentNotFound
from app.services.document_service import DocumentService
from app.tasks.background import enqueue_task
from app.schemas import (
    DocumentResponse, DocumentListResponse, DocumentUploadResponse,
    AsyncUploadResponse, DocumentChunksResponse, ChunkResponse,
    DocumentContentResponse, DocumentReindexResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def process_document_background(
    session_id: str,
    file_path: str,
    collection_id: str,
    user_id: str,
    filename: str,
    file_size: int,
    db_url: str
):
    """Background task to process document."""
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        logger.info(f"Background processing started: {session_id}")

        # Process the document
        doc_id = DocumentService.process_document(
            db, file_path, collection_id, user_id, filename, file_size
        )

        # Update session to completed
        UploadSessionCRUD.link_document_to_session(db, session_id, doc_id)
        UploadSessionCRUD.update_session_progress(db, session_id, 100, "completed")

        logger.info(f"Background processing completed: {session_id} -> {doc_id}")

    except Exception as e:
        logger.error(f"Background processing failed: {session_id}", exc_info=True)
        UploadSessionCRUD.update_session_error(db, session_id, str(e))
    finally:
        db.close()


@router.post("/upload", response_model=DocumentUploadResponse | AsyncUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    collection_id: str = Form("default"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and index a document."""
    # Verify collection exists and belongs to user
    collection = CollectionCRUD.get_collection(db, collection_id, current_user.id)
    if not collection:
        raise CollectionNotFound(collection_id)

    # Validate file
    file_size = len(await file.read())
    await file.seek(0)  # Reset file pointer

    DocumentService.validate_file(file.filename, file_size)

    # Check if async upload
    is_async = DocumentService.is_async_upload(file_size)

    if is_async:
        # Create upload session for async processing
        session = UploadSessionCRUD.create_session(
            db, current_user.id, collection_id, file.filename, file_size
        )

        # Save file
        file_path = DocumentService.save_upload_file(file)

        # Queue background task
        from app.core.config import settings
        enqueue_task(
            task_id=session.id,
            func=process_document_background,
            session_id=session.id,
            file_path=file_path,
            collection_id=collection_id,
            user_id=current_user.id,
            filename=file.filename,
            file_size=file_size,
            db_url=settings.DATABASE_URL
        )

        logger.info(f"Queued async upload: {session.id}")

        return AsyncUploadResponse(
            status="processing",
            session_id=session.id,
            filename=file.filename,
            file_size=file_size,
            estimated_time_seconds=60,
            status_url=f"/api/v1/uploads/{session.id}/status"
        )

    else:
        # Synchronous upload
        file_path = DocumentService.save_upload_file(file)

        try:
            doc_id = DocumentService.process_document(
                db, file_path, collection_id, current_user.id,
                file.filename, file_size
            )

            doc = DocumentCRUD.get_document(db, doc_id, current_user.id)

            return DocumentUploadResponse(
                status="success",
                document_id=doc.id,
                filename=doc.filename,
                file_size=doc.file_size,
                chunks_created=doc.chunks_count,
                indexed_at=doc.indexed_at
            )
        except Exception as e:
            raise


@router.get("", response_model=DocumentListResponse)
def list_documents(
    collection_id: str = "default",
    offset: int = 0,
    limit: int = 50,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List documents in a collection with pagination."""
    if offset < 0 or limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset must be >= 0, limit must be 1-1000"
        )

    collection = CollectionCRUD.get_collection(db, collection_id, current_user.id)
    if not collection:
        raise CollectionNotFound(collection_id)

    # Get total count
    total = db.query(Document).filter(
        Document.collection_id == collection_id,
        Document.user_id == current_user.id
    ).count()

    # Get paginated results
    documents = db.query(Document).filter(
        Document.collection_id == collection_id,
        Document.user_id == current_user.id
    ).order_by(Document.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "documents": documents,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document details."""
    doc = DocumentCRUD.get_document(db, doc_id, current_user.id)
    if not doc:
        raise DocumentNotFound(doc_id)
    return doc


@router.get("/{doc_id}/chunks", response_model=DocumentChunksResponse)
def get_document_chunks(
    doc_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all chunks for a document."""
    doc = DocumentCRUD.get_document(db, doc_id, current_user.id)
    if not doc:
        raise DocumentNotFound(doc_id)

    chunks = ChunkCRUD.list_document_chunks(db, doc_id)
    chunk_responses = [
        ChunkResponse(
            id=chunk.id,
            content=chunk.content,
            chunk_index=chunk.chunk_index,
            metadata={"token_count": chunk.token_count, "vector_id": chunk.vector_id}
        )
        for chunk in chunks
    ]

    return DocumentChunksResponse(
        document_id=doc_id,
        filename=doc.filename,
        chunks=chunk_responses,
        total_chunks=len(chunk_responses)
    )


@router.get("/{doc_id}/content", response_model=DocumentContentResponse)
def get_document_content(
    doc_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get raw document content."""
    doc = DocumentCRUD.get_document(db, doc_id, current_user.id)
    if not doc:
        raise DocumentNotFound(doc_id)

    if not doc.content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document content not available (may need to be reindexed)"
        )

    return DocumentContentResponse(
        document_id=doc_id,
        filename=doc.filename,
        content=doc.content,
        char_count=len(doc.content)
    )


@router.post("/{doc_id}/reindex", response_model=DocumentReindexResponse)
def reindex_document(
    doc_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reindex a document from stored content."""
    doc = DocumentCRUD.get_document(db, doc_id, current_user.id)
    if not doc:
        raise DocumentNotFound(doc_id)

    if not doc.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no stored content to reindex"
        )

    # Reindex
    from app.services.rag_service import get_rag_service
    rag_service = get_rag_service()

    # Delete existing chunks from DB
    db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
    db.commit()

    # Reindex from raw content
    chunks = rag_service.reindex_document(
        raw_content=doc.content,
        collection_id=doc.collection_id,
        document_id=doc_id,
        filename=doc.filename
    )

    # Update document status
    DocumentCRUD.update_document_status(
        db, doc_id, DocumentStatus.INDEXED, len(chunks)
    )

    return DocumentReindexResponse(
        document_id=doc_id,
        chunks_created=len(chunks),
        indexed_at=doc.indexed_at
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document."""
    doc = DocumentCRUD.get_document(db, doc_id, current_user.id)
    if not doc:
        raise DocumentNotFound(doc_id)

    # Delete from vector store and BM25 index
    from app.services.rag_service import get_rag_service
    rag_service = get_rag_service()
    rag_service.delete_document(doc_id)

    # Delete from database
    DocumentCRUD.delete_document(db, doc_id, current_user.id)
    return None
