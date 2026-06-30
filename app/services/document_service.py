import shutil
import tempfile
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import InvalidFileType, FileTooLarge
from app.db.crud import DocumentCRUD, UploadSessionCRUD
from app.db.models import DocumentStatus, UploadSessionStatus
from app.services.rag_service import get_rag_service


class DocumentService:
    @staticmethod
    def validate_file(filename: str, file_size: int):
        """Validate file extension and size."""
        # Check file extension
        ext = Path(filename).suffix.lstrip(".").lower()
        allowed = settings.allowed_extensions_list
        if ext not in allowed:
            raise InvalidFileType(filename, allowed)

        # Check file size (convert MB to bytes)
        max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size_bytes:
            raise FileTooLarge(settings.MAX_FILE_SIZE_MB)

    @staticmethod
    def is_async_upload(file_size: int) -> bool:
        """Determine if upload should be async based on file size."""
        threshold_bytes = settings.ASYNC_THRESHOLD_MB * 1024 * 1024
        return file_size > threshold_bytes

    @staticmethod
    def process_document(
        db: Session,
        file_path: str,
        collection_id: str,
        user_id: str,
        filename: str,
        file_size: int
    ) -> str:
        """Process document: load, chunk, and index. Returns document ID."""
        rag_service = get_rag_service()

        # Create document record
        doc = DocumentCRUD.create_document(
            db, collection_id, user_id, filename, file_size
        )

        try:
            # Load document
            docs = rag_service.load_document(file_path)

            # Store raw content for reindexing
            if docs:
                raw_content = docs[0].content
                DocumentCRUD.update_document_content(db, doc.id, raw_content)

            # Chunk document with collection and document IDs
            chunks = rag_service.chunk_document(
                docs,
                source_name=filename,
                document_id=doc.id,
                collection_id=collection_id
            )

            # Index chunks
            rag_service.index_chunks(chunks)

            # Update document status
            DocumentCRUD.update_document_status(
                db, doc.id, DocumentStatus.INDEXED, len(chunks)
            )

            return doc.id
        except Exception as e:
            DocumentCRUD.update_document_status(
                db, doc.id, DocumentStatus.FAILED
            )
            raise
        finally:
            # Clean up temp file
            if Path(file_path).exists():
                Path(file_path).unlink()

    @staticmethod
    def save_upload_file(uploaded_file) -> str:
        """Save uploaded file to temp directory and return path."""
        temp_dir = Path(settings.TEMP_UPLOAD_DIR)
        temp_dir.mkdir(exist_ok=True)

        with tempfile.NamedTemporaryFile(
            dir=temp_dir,
            suffix=Path(uploaded_file.filename).suffix,
            delete=False
        ) as tmp:
            tmp.write(uploaded_file.file.read())
            return tmp.name

    @staticmethod
    def cleanup_file(file_path: str):
        """Delete file."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
        except Exception:
            pass
