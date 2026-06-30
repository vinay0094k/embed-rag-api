from typing import List, Optional
import logging
import threading
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import asyncio

# Import RAG components from local copy
from app.rag_components.vector_store import HybridVectorStore
from app.rag_components.chunker import StructureAwareChunker, ChunkMetadata
from app.rag_components.document_loader import DocumentLoader
from app.rag_components.bm25_index import BM25Index
from app.rag_components.models import DocumentChunk, RetrievalResult

from app.core.config import settings
from app.core.exceptions import SearchError, ChunkingError
from app.services.embedding_service import build_embeddings
from app.services.reranker_service import build_reranker
from app.services.expansion_service import QueryExpansionService

logger = logging.getLogger(__name__)


class ReadWriteLock:
    """Simple read-write lock allowing concurrent reads, exclusive writes."""

    def __init__(self):
        self._read_ready = threading.Condition(threading.RLock())
        self._readers = 0

    @contextmanager
    def read_lock(self):
        """Acquire read lock (shared)."""
        self._read_ready.acquire()
        try:
            self._readers += 1
        finally:
            self._read_ready.release()
        try:
            yield
        finally:
            self._read_ready.acquire()
            try:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notify_all()
            finally:
                self._read_ready.release()

    @contextmanager
    def write_lock(self):
        """Acquire write lock (exclusive)."""
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()
        try:
            yield
        finally:
            self._read_ready.release()


class RAGService:
    def __init__(self):
        logger.info(f"Initializing RAG Service with {settings.EMBEDDINGS_PROVIDER} embeddings")
        self.embeddings = build_embeddings()
        self.reranker = build_reranker()
        self.vector_store = HybridVectorStore(
            persist_dir=settings.CHROMA_DB_PATH,
            embedding_fn=self.embeddings.embed_batch,
        )
        self.bm25 = BM25Index()
        self.chunker = StructureAwareChunker()
        self.document_loader = DocumentLoader()

        # Thread safety for in-memory index operations (read-write lock for concurrent reads)
        self._bm25_lock = ReadWriteLock()

    def load_document(self, file_path: str):
        """Load document from file path."""
        try:
            # DocumentLoader.load_file() returns RawDocument, convert to list for compatibility
            doc = self.document_loader.load_file(file_path)
            if doc:
                return [doc]
            return []
        except Exception as e:
            raise ChunkingError(f"Failed to load document: {str(e)}")

    def chunk_document(
        self,
        docs: list,
        source_name: str = "document",
        document_id: str = "",
        collection_id: str = ""
    ) -> List[DocumentChunk]:
        """Chunk documents into smaller pieces."""
        try:
            all_chunks = []
            for doc in docs:
                # Create metadata for the document
                metadata = ChunkMetadata(
                    source_path=getattr(doc, 'file_path', ''),
                    source_name=getattr(doc, 'file_name', source_name),
                    source_type=getattr(doc, 'file_extension', 'txt').lower(),
                    document_id=document_id,
                    collection_id=collection_id
                )
                # Chunk with metadata
                chunks = self.chunker.chunk(doc, metadata)
                all_chunks.extend(chunks)
            return all_chunks
        except Exception as e:
            raise ChunkingError(f"Failed to chunk document: {str(e)}")

    def index_chunks(self, chunks: List[DocumentChunk]):
        """Index chunks into vector store and BM25 (thread-safe, write-exclusive)."""
        try:
            if not chunks:
                return
            # Add all chunks at once to vector store
            self.vector_store.add_chunks(chunks)
            # Protect in-memory BM25Index with exclusive write lock
            with self._bm25_lock.write_lock():
                self.bm25.add_documents(chunks)
        except Exception as e:
            raise ChunkingError(f"Failed to index chunks: {str(e)}")

    def search(
        self,
        query: str,
        collection_id: str = "default",
        top_k: int = None,
        threshold: float = None,
        alpha: float = None,
        use_rerank: bool = False,
        use_query_expansion: bool = None,
        filters: Optional[object] = None
    ) -> List[RetrievalResult]:
        """Search knowledge base for relevant documents with optional reranking and filters (thread-safe)."""
        try:
            top_k = top_k or settings.DEFAULT_TOP_K
            threshold = threshold or settings.SIMILARITY_THRESHOLD
            alpha = alpha or settings.HYBRID_SEARCH_ALPHA

            # Determine if expansion should be used
            should_expand = False
            if use_query_expansion is None:
                should_expand = settings.QUERY_EXPANSION_ENABLED
            else:
                should_expand = use_query_expansion

            # Generate query variants if expansion enabled
            queries_to_search = [query]
            if should_expand:
                try:
                    variants = asyncio.run(
                        QueryExpansionService.generate_variants(
                            query,
                            num_variants=settings.QUERY_EXPANSION_NUM_VARIANTS,
                            timeout=settings.QUERY_EXPANSION_TIMEOUT
                        )
                    )
                    if variants:
                        queries_to_search.extend(variants)
                        logger.info(f"Generated {len(variants)} query variants for expansion")
                except Exception as e:
                    logger.warning(f"Query expansion failed, continuing with original query: {e}")

            # Search with all queries in parallel if expansion is used
            if len(queries_to_search) > 1:
                all_results = []
                with ThreadPoolExecutor(max_workers=min(4, len(queries_to_search))) as executor:
                    search_tasks = [
                        executor.submit(
                            self._perform_single_search,
                            q, filters, top_k * 2, alpha, use_rerank
                        )
                        for q in queries_to_search
                    ]
                    for future in search_tasks:
                        all_results.extend(future.result())

                # Merge results: deduplicate by chunk ID, keep max score
                chunk_map = {}
                for result in all_results:
                    chunk_id = result.chunk.id
                    if chunk_id not in chunk_map or result.score > chunk_map[chunk_id][0]:
                        chunk_map[chunk_id] = (result.score, result)

                merged = [r for _, r in sorted(chunk_map.values(), key=lambda x: x[0], reverse=True)]
                results = merged[:top_k]
            else:
                # Single query: use direct search
                results = self._perform_single_search(query, filters, top_k, alpha, use_rerank)

            # Rerank results if reranker available (outside lock since it's async and doesn't touch BM25)
            if use_rerank and self.reranker and results:
                logger.info(f"Reranking {len(results)} results for query: {query}")
                documents = [r.chunk.content for r in results]
                reranked = self.reranker.rerank(query, documents, top_k=top_k)

                # Map reranked results back to original format
                reranked_dict = {doc: score for doc, score in reranked}
                results = [
                    r for r in results
                    if r.chunk.content in reranked_dict
                ]
                results.sort(
                    key=lambda x: reranked_dict.get(x.chunk.content, 0),
                    reverse=True
                )

            return results[:top_k]
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            raise SearchError(f"Search failed: {str(e)}")

    def _perform_single_search(
        self,
        query: str,
        filters: Optional[object],
        top_k: int,
        alpha: float,
        use_rerank: bool
    ) -> List[RetrievalResult]:
        """Perform a single search query (helper for parallel expansion searches)."""
        with self._bm25_lock.read_lock():
            search_k = top_k * 2 if use_rerank and self.reranker else top_k
            results = self.vector_store.hybrid_search(
                query=query,
                filters=filters,
                top_k=search_k,
                final_top_k=top_k,
                vector_weight=alpha,
                bm25_weight=1 - alpha
            )
        return results

    def delete_document(self, doc_id: str):
        """Delete document from vector store and BM25 index."""
        try:
            logger.info(f"Deleting document {doc_id} from RAG indices")
            deleted_count = self.vector_store.delete_by_document_id(doc_id)
            logger.info(f"Deleted {deleted_count} chunks for document {doc_id}")
        except Exception as e:
            raise SearchError(f"Failed to delete document: {str(e)}")

    def delete_collection(self, collection_id: str):
        """Delete all documents in a collection from vector store and BM25 index."""
        try:
            logger.info(f"Deleting collection {collection_id} from RAG indices")
            deleted_count = self.vector_store.delete_by_collection_id(collection_id)
            logger.info(f"Deleted {deleted_count} chunks for collection {collection_id}")
        except Exception as e:
            raise SearchError(f"Failed to delete collection: {str(e)}")

    def reindex_document(
        self,
        raw_content: str,
        collection_id: str,
        document_id: str,
        filename: str
    ) -> List[DocumentChunk]:
        """Reindex document from raw content."""
        try:
            # Delete from vector store and BM25
            logger.info(f"Reindexing document {document_id}")
            self.delete_document(document_id)

            # Chunk the raw content
            from app.rag_components.models import RawDocument
            raw_doc = RawDocument(
                file_path=filename,
                file_name=filename,
                file_extension=filename.split('.')[-1] if '.' in filename else 'txt',
                content=raw_content,
                file_size=len(raw_content.encode('utf-8')),
                doc_modified_at='',
            )

            chunks = self.chunk_document(
                [raw_doc],
                source_name=filename,
                document_id=document_id,
                collection_id=collection_id
            )

            # Index new chunks
            self.index_chunks(chunks)
            logger.info(f"Reindexed document {document_id} with {len(chunks)} chunks")
            return chunks
        except Exception as e:
            raise SearchError(f"Failed to reindex document: {str(e)}")


# Singleton instance with thread safety
_rag_service_instance = None
_rag_service_lock = threading.Lock()


def get_rag_service() -> RAGService:
    """Get or create RAG service instance (thread-safe).

    Uses double-checked locking pattern to minimize lock contention.
    """
    global _rag_service_instance

    # First check without lock (fast path)
    if _rag_service_instance is not None:
        return _rag_service_instance

    # Acquire lock for initialization
    with _rag_service_lock:
        # Double-check after acquiring lock
        if _rag_service_instance is None:
            logger.info("Creating RAG service singleton")
            _rag_service_instance = RAGService()

    return _rag_service_instance
