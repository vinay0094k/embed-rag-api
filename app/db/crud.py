from sqlalchemy.orm import Session
from app.db.models import (
    User, APIKey, Collection, Document, DocumentStatus,
    UploadSession, UploadSessionStatus, Chunk
)
from app.core.security import generate_api_key
from app.core.crypto import hash_api_key, verify_api_key
import uuid


class UserCRUD:
    @staticmethod
    def create_user(db: Session, username: str, email: str) -> User:
        user = User(id=str(uuid.uuid4()), username=username, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> User:
        return db.query(User).filter(User.id == user_id).first()


class APIKeyCRUD:
    @staticmethod
    def create_api_key(db: Session, user_id: str) -> str:
        """Create new API key. Returns plain key (displayed once), stores hash."""
        key = generate_api_key()
        key_hash = hash_api_key(key)
        api_key = APIKey(
            id=str(uuid.uuid4()),
            user_id=user_id,
            key=key,
            key_hash=key_hash
        )
        db.add(api_key)
        db.commit()
        return key  # Return plain key for display (only shown once)

    @staticmethod
    def get_api_key(db: Session, key: str) -> APIKey:
        """Find API key by verifying hash (not by plain key)."""
        key_hash = hash_api_key(key)
        return db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.active == True
        ).first()

    @staticmethod
    def list_user_api_keys(db: Session, user_id: str):
        """List all API keys for a user (active and inactive)."""
        return db.query(APIKey).filter(APIKey.user_id == user_id).order_by(APIKey.created_at.desc()).all()

    @staticmethod
    def get_api_key_by_id(db: Session, key_id: str, user_id: str) -> APIKey:
        """Get API key by ID (ownership check)."""
        return db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == user_id
        ).first()

    @staticmethod
    def revoke_api_key(db: Session, key_id: str, user_id: str) -> bool:
        """Revoke an API key (soft delete via active flag)."""
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == user_id
        ).first()
        if api_key:
            api_key.active = False
            db.commit()
            return True
        return False


class CollectionCRUD:
    @staticmethod
    def create_collection(db: Session, user_id: str, name: str, description: str = None) -> Collection:
        collection = Collection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description
        )
        db.add(collection)
        db.commit()
        db.refresh(collection)
        return collection

    @staticmethod
    def get_collection(db: Session, collection_id: str, user_id: str) -> Collection:
        return db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == user_id
        ).first()

    @staticmethod
    def list_user_collections(db: Session, user_id: str):
        return db.query(Collection).filter(Collection.user_id == user_id).all()

    @staticmethod
    def get_collection_stats(db: Session, collection_id: str, user_id: str) -> dict:
        """Get collection statistics. Count actual chunks from Chunk table for accuracy."""
        from sqlalchemy import func
        from app.db.models import Chunk

        collection = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == user_id
        ).first()
        if not collection:
            return None

        # Query document counts and total file size
        doc_stats_query = db.query(
            func.count(Document.id).label('document_count'),
            func.sum(Document.file_size).label('total_size_bytes'),
            func.max(Document.indexed_at).label('last_indexed_at')
        ).filter(Document.collection_id == collection_id).first()

        # Count actual chunks from Chunk table (source of truth)
        # This is more accurate than summing Document.chunks_count
        total_chunks_result = db.query(
            func.count(Chunk.id).label('total_chunks')
        ).join(Document, Chunk.document_id == Document.id).filter(
            Document.collection_id == collection_id
        ).first()

        total_chunks = total_chunks_result.total_chunks or 0 if total_chunks_result else 0

        # Count by status
        status_counts = db.query(
            Document.status,
            func.count(Document.id).label('count')
        ).filter(Document.collection_id == collection_id).group_by(Document.status).all()

        status_dict = {status.value: count for status, count in status_counts}

        return {
            'collection_id': collection_id,
            'document_count': doc_stats_query.document_count or 0,
            'total_chunks': total_chunks,
            'total_size_bytes': doc_stats_query.total_size_bytes or 0,
            'status_counts': status_dict,
            'last_indexed_at': doc_stats_query.last_indexed_at,
            'created_at': collection.created_at
        }

    @staticmethod
    def update_collection(
        db: Session, collection_id: str, user_id: str, name: str = None, description: str = None
    ) -> Collection:
        collection = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == user_id
        ).first()
        if collection:
            if name is not None:
                collection.name = name
            if description is not None:
                collection.description = description
            db.commit()
            db.refresh(collection)
        return collection

    @staticmethod
    def delete_collection(db: Session, collection_id: str, user_id: str) -> bool:
        result = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == user_id
        ).delete()
        db.commit()
        return result > 0


class DocumentCRUD:
    @staticmethod
    def create_document(
        db: Session, collection_id: str, user_id: str,
        filename: str, file_size: int
    ) -> Document:
        doc = Document(
            id=str(uuid.uuid4()),
            collection_id=collection_id,
            user_id=user_id,
            filename=filename,
            file_size=file_size,
            status=DocumentStatus.PENDING
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def get_document(db: Session, doc_id: str, user_id: str) -> Document:
        return db.query(Document).filter(
            Document.id == doc_id,
            Document.user_id == user_id
        ).first()

    @staticmethod
    def list_collection_documents(db: Session, collection_id: str, user_id: str):
        return db.query(Document).filter(
            Document.collection_id == collection_id,
            Document.user_id == user_id
        ).all()

    @staticmethod
    def update_document_status(
        db: Session, doc_id: str, status: DocumentStatus,
        chunks_count: int = None
    ):
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = status
            if chunks_count is not None:
                doc.chunks_count = chunks_count
            if status == DocumentStatus.INDEXED:
                from datetime import datetime
                doc.indexed_at = datetime.utcnow()
            db.commit()
            db.refresh(doc)
        return doc

    @staticmethod
    def update_document_content(db: Session, doc_id: str, content: str) -> Document:
        """Store raw document content for reindexing."""
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.content = content
            db.commit()
            db.refresh(doc)
        return doc

    @staticmethod
    def delete_document(db: Session, doc_id: str, user_id: str) -> bool:
        result = db.query(Document).filter(
            Document.id == doc_id,
            Document.user_id == user_id
        ).delete()
        db.commit()
        return result > 0


class UploadSessionCRUD:
    @staticmethod
    def create_session(
        db: Session, user_id: str, collection_id: str,
        filename: str, file_size: int
    ) -> UploadSession:
        session = UploadSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            collection_id=collection_id,
            filename=filename,
            file_size=file_size,
            status=UploadSessionStatus.UPLOADING
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_session(db: Session, session_id: str, user_id: str) -> UploadSession:
        return db.query(UploadSession).filter(
            UploadSession.id == session_id,
            UploadSession.user_id == user_id
        ).first()

    @staticmethod
    def update_session_progress(
        db: Session, session_id: str, progress: int, status: UploadSessionStatus = None
    ):
        session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
        if session:
            session.progress_percent = progress
            if status:
                session.status = status
            if status == UploadSessionStatus.COMPLETED:
                from datetime import datetime
                session.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
        return session

    @staticmethod
    def update_session_error(db: Session, session_id: str, error: str):
        session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
        if session:
            session.status = UploadSessionStatus.FAILED
            session.error_message = error
            from datetime import datetime
            session.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
        return session

    @staticmethod
    def link_document_to_session(db: Session, session_id: str, doc_id: str):
        session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
        if session:
            session.document_id = doc_id
            db.commit()


class ChunkCRUD:
    @staticmethod
    def list_document_chunks(db: Session, doc_id: str) -> list:
        return db.query(Chunk).filter(Chunk.document_id == doc_id).order_by(Chunk.chunk_index).all()
