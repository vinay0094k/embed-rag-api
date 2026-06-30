import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
import logging

from app.db.database import get_db
from app.db.crud import CollectionCRUD
from app.core.security import get_current_user
from app.core.exceptions import CollectionNotFound
from app.services.rag_service import get_rag_service
from app.schemas import SearchRequest, SearchResponse, SearchResultItem, BatchSearchRequest, BatchSearchResponse, SuggestResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    request: SearchRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search knowledge base with optional metadata filters."""
    # Verify user has access to this collection
    collection = CollectionCRUD.get_collection(
        db, request.collection_id, current_user.id
    )
    if not collection:
        raise CollectionNotFound(request.collection_id)

    # Build metadata filter if any filters provided
    from app.rag_components.models import MetadataFilter
    filters = None
    if any([
        request.source_type, request.source_name, request.service_name,
        request.environment, request.team, request.tags, request.chunk_type,
        request.chunk_language, request.severity
    ]):
        filters = MetadataFilter(
            source_type=request.source_type,
            source_name=request.source_name,
            service_name=request.service_name,
            environment=request.environment,
            team=request.team,
            tags=request.tags,
            chunk_type=request.chunk_type,
            chunk_language=request.chunk_language,
            severity=request.severity
        )

    # Perform search
    start_time = time.time()
    rag_service = get_rag_service()
    results = rag_service.search(
        query=request.query,
        collection_id=request.collection_id,
        top_k=request.top_k,
        threshold=request.threshold,
        use_query_expansion=request.use_query_expansion,
        filters=filters
    )
    search_time = (time.time() - start_time) * 1000  # Convert to ms

    # Format results
    formatted_results = [
        SearchResultItem(
            content=result.chunk.content,
            source=result.chunk.metadata.source_name if result.chunk.metadata else "unknown",
            score=result.score,
            metadata=result.chunk.metadata.model_dump() if result.chunk.metadata else None
        )
        for result in results
    ]

    return SearchResponse(
        query=request.query,
        results=formatted_results,
        search_time_ms=search_time,
        result_count=len(formatted_results)
    )


@router.post("/batch", response_model=BatchSearchResponse)
def batch_search(
    request: BatchSearchRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search knowledge base with multiple queries and optional filters."""
    # Verify user has access to this collection
    collection = CollectionCRUD.get_collection(
        db, request.collection_id, current_user.id
    )
    if not collection:
        raise CollectionNotFound(request.collection_id)

    # Build metadata filter if any filters provided
    from app.rag_components.models import MetadataFilter
    filters = None
    if any([
        request.source_type, request.source_name, request.service_name,
        request.environment, request.team, request.tags, request.chunk_type,
        request.chunk_language, request.severity
    ]):
        filters = MetadataFilter(
            source_type=request.source_type,
            source_name=request.source_name,
            service_name=request.service_name,
            environment=request.environment,
            team=request.team,
            tags=request.tags,
            chunk_type=request.chunk_type,
            chunk_language=request.chunk_language,
            severity=request.severity
        )

    # Perform searches in parallel (queries are independent)
    start_time = time.time()
    rag_service = get_rag_service()

    def search_query(query: str):
        """Search single query (runs in thread pool)."""
        results = rag_service.search(
            query=query,
            collection_id=request.collection_id,
            top_k=request.top_k,
            threshold=request.threshold,
            use_query_expansion=request.use_query_expansion,
            filters=filters
        )

        # Format results
        formatted_results = [
            SearchResultItem(
                content=result.chunk.content,
                source=result.chunk.metadata.source_name if result.chunk.metadata else "unknown",
                score=result.score,
                metadata=result.chunk.metadata.model_dump() if result.chunk.metadata else None
            )
            for result in results
        ]

        return SearchResponse(
            query=query,
            results=formatted_results,
            search_time_ms=0,
            result_count=len(formatted_results)
        )

    # Run queries in parallel (up to 4 workers, limited by I/O and embedding cache)
    all_results = []
    max_workers = min(4, len(request.queries))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        all_results = list(executor.map(search_query, request.queries))

    total_time = (time.time() - start_time) * 1000
    logger.info(f"Batch search completed: {len(request.queries)} queries in {total_time:.0f}ms")

    return BatchSearchResponse(
        results=all_results,
        total_queries=len(request.queries),
        total_time_ms=total_time
    )


@router.get("/suggest", response_model=SuggestResponse)
def suggest_terms(
    q: str,
    top_k: int = 10,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get autocomplete suggestions from indexed terms."""
    rag_service = get_rag_service()
    suggestions = rag_service.bm25.suggest_terms(q, top_k)

    return SuggestResponse(
        query=q,
        suggestions=suggestions,
        suggestion_count=len(suggestions)
    )
