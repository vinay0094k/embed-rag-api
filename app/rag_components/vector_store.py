import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import chromadb

from app.rag_components.embeddings import DefaultEmbeddings, build_embeddings
from app.rag_components.models import (
    ChunkMetadata,
    DocumentChunk,
    MetadataFilter,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


class HybridVectorStore:
    def __init__(
        self,
        persist_dir: str = "./chroma_db",
        collection_name: str = "rag_documents",
        embedding_fn: Optional[Callable] = None,
        query_embedding_fn: Optional[Callable] = None,
        bm25_index: Optional[Any] = None,
        hnsw_space: str = "cosine",
    ):
        self.chroma = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.chroma.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": hnsw_space},
        )
        self.embedding_fn = embedding_fn or self._default_embedding_fn
        # query_embedding_fn is used for retrieval; falls back to embedding_fn if not set
        self.query_embedding_fn = query_embedding_fn or self.embedding_fn
        self.bm25 = bm25_index

    def _default_embedding_fn(self, texts: List[str]) -> List[List[float]]:
        emb = DefaultEmbeddings()
        return emb.embed(texts)

    def _prepare_metadata_for_chroma(self, metadata: ChunkMetadata) -> Dict[str, Any]:
        """Convert ChunkMetadata to Chroma-compatible format."""
        meta_dict = {}
        for key, value in metadata.model_dump().items():
            if value is None:
                meta_dict[key] = ""
            elif isinstance(value, list):
                # Convert lists to comma-separated strings for Chroma
                meta_dict[key] = ",".join(str(v) for v in value)
            elif isinstance(value, dict):
                meta_dict[key] = json.dumps(value)
            else:
                meta_dict[key] = str(value) if not isinstance(value, (str, int, float, bool)) else value
        return meta_dict

    def _reconstruct_metadata_from_chroma(self, meta_dict: Dict[str, Any]) -> ChunkMetadata:
        """Reconstruct ChunkMetadata from Chroma metadata dict."""
        # Handle tags field if it's stored as a comma-separated string
        if "tags" in meta_dict and isinstance(meta_dict["tags"], str):
            meta_dict["tags"] = [t.strip() for t in meta_dict["tags"].split(",") if t.strip()]
        return ChunkMetadata(**meta_dict)

    def add_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        if not chunks:
            logger.debug("add_chunks called with empty list")
            return

        logger.info("Adding %d chunks to vector store", len(chunks))
        ids = [c.id for c in chunks]
        texts = [c.content for c in chunks]
        if embeddings is None:
            embeddings = self.embedding_fn(texts)
        metadatas = [self._prepare_metadata_for_chroma(c.metadata) for c in chunks]
        documents = texts

        # Detect dimension mismatch before hitting ChromaDB's cryptic error
        existing_count = self.collection.count()
        if existing_count > 0 and embeddings:
            sample = self.collection.get(limit=1, include=["embeddings"])
            sample_embs = sample.get("embeddings")
            if sample_embs is not None and len(sample_embs) > 0 and sample_embs[0] is not None and len(sample_embs[0]) > 0:
                existing_dim = len(sample_embs[0])
                new_dim = len(embeddings[0])
                if existing_dim != new_dim:
                    raise RuntimeError(
                        f"Embedding dimension mismatch: collection '{self.collection.name}' "
                        f"stores {existing_dim}-dim vectors but the current model produces "
                        f"{new_dim}-dim vectors. Run 'rag reset' (or click Reset in the UI) "
                        f"to clear the collection, then re-index your documents."
                    )

        # ChromaDB hard limit is 5461 items per add() call
        chroma_batch = 5000
        for i in range(0, len(ids), chroma_batch):
            self.collection.add(
                ids=ids[i : i + chroma_batch],
                embeddings=embeddings[i : i + chroma_batch],
                metadatas=metadatas[i : i + chroma_batch],
                documents=documents[i : i + chroma_batch],
            )
            logger.debug("ChromaDB add: batch %d-%d / %d", i, min(i + chroma_batch, len(ids)), len(ids))

        if self.bm25 is not None:
            self.bm25.add_documents(chunks)
            logger.debug("Also added %d chunks to BM25 index", len(chunks))

    def update_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Update existing chunks by ID (delete + add)."""
        logger.info("Updating %d chunks", len(chunks))
        ids = [c.id for c in chunks]
        self.collection.delete(ids=ids)

        if self.bm25 is not None:
            self.bm25.remove_documents(set(ids))

        self.add_chunks(chunks)

    def delete_by_source_path(self, source_path: str) -> None:
        """Delete all chunks from a given source file."""
        logger.info("Deleting chunks for source: %s", source_path)
        results = self.collection.get(
            where={"source_path": {"$eq": source_path}},
        )
        if results["ids"]:
            logger.debug("Found %d chunks to delete", len(results["ids"]))
            self.collection.delete(ids=results["ids"])
            if self.bm25 is not None:
                self.bm25.remove_documents(set(results["ids"]))
        else:
            logger.debug("No chunks found for source: %s", source_path)

    def delete_by_document_id(self, document_id: str) -> int:
        """Delete all chunks for a specific document."""
        logger.info("Deleting chunks for document_id: %s", document_id)
        results = self.collection.get(
            where={"document_id": {"$eq": document_id}},
        )
        if results["ids"]:
            deleted_count = len(results["ids"])
            logger.debug("Found %d chunks to delete for document", deleted_count)
            self.collection.delete(ids=results["ids"])
            if self.bm25 is not None:
                self.bm25.remove_documents(set(results["ids"]))
            return deleted_count
        else:
            logger.debug("No chunks found for document_id: %s", document_id)
            return 0

    def delete_by_collection_id(self, collection_id: str) -> int:
        """Delete all chunks for a specific collection."""
        logger.info("Deleting chunks for collection_id: %s", collection_id)
        results = self.collection.get(
            where={"collection_id": {"$eq": collection_id}},
        )
        if results["ids"]:
            deleted_count = len(results["ids"])
            logger.debug("Found %d chunks to delete for collection", deleted_count)
            self.collection.delete(ids=results["ids"])
            if self.bm25 is not None:
                self.bm25.remove_documents(set(results["ids"]))
            return deleted_count
        else:
            logger.debug("No chunks found for collection_id: %s", collection_id)
            return 0

    def _vector_search(
        self,
        query: str,
        where_clause: Optional[Dict[str, Any]],
        top_k: int,
        search_type: str = "similarity",
    ) -> List[RetrievalResult]:
        logger.debug("Vector search: search_type=%s, top_k=%d", search_type, top_k)
        query_embedding = self.query_embedding_fn([query])

        kwargs: Dict[str, Any] = {
            "query_embeddings": query_embedding,
            "n_results": top_k,
        }
        if where_clause:
            kwargs["where"] = where_clause

        # Note: ChromaDB doesn't support mmr_lambda in query() - use similarity and rerank if needed
        results = self.collection.query(**kwargs)

        retrieval_results = []
        for i in range(len(results["ids"][0])):
            chunk_id = results["ids"][0][i]
            distance = results["distances"][0][i]
            metadata = self._reconstruct_metadata_from_chroma(results["metadatas"][0][i])

            chunk = DocumentChunk(
                id=chunk_id,
                content=results["documents"][0][i],
                metadata=metadata,
            )
            retrieval_results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=1.0 - distance if distance <= 1.0 else 0.0,
                    vector_score=1.0 - distance,
                )
            )

        logger.debug("Vector search returned %d results", len(retrieval_results))
        return retrieval_results

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievalResult],
        bm25_results: List[Tuple[str, float]],
        final_top_k: int,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        rrf_k: int = 60,
    ) -> List[RetrievalResult]:
        vector_ranks = {r.chunk.id: i + 1 for i, r in enumerate(vector_results)}
        bm25_ranks = {doc_id: i + 1 for i, (doc_id, _) in enumerate(bm25_results)}

        all_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())

        fused_scores: Dict[str, float] = {}
        for doc_id in all_ids:
            score = 0.0
            if doc_id in vector_ranks:
                score += vector_weight / (rrf_k + vector_ranks[doc_id])
            if doc_id in bm25_ranks:
                score += bm25_weight / (rrf_k + bm25_ranks[doc_id])
            fused_scores[doc_id] = score

        sorted_ids = sorted(
            fused_scores.keys(),
            key=lambda x: fused_scores[x],
            reverse=True,
        )
        top_ids = sorted_ids[:final_top_k]

        id_to_vector = {r.chunk.id: r for r in vector_results}
        id_to_bm25 = dict(bm25_results)

        results = []
        for doc_id in top_ids:
            chunk = id_to_vector[doc_id].chunk if doc_id in id_to_vector else None
            if chunk is None:
                continue

            results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=fused_scores[doc_id],
                    vector_score=id_to_vector[doc_id].score if doc_id in id_to_vector else None,
                    bm25_score=id_to_bm25.get(doc_id),
                    fused_score=fused_scores[doc_id],
                )
            )

        return results

    def hybrid_search(
        self,
        query: str,
        filters: Optional[MetadataFilter] = None,
        top_k: int = 20,
        final_top_k: int = 5,
        search_type: str = "mmr",
        mmr_lambda: float = 0.5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        rrf_k: int = 60,
    ) -> List[RetrievalResult]:
        logger.info(
            "Hybrid search: query=%s, top_k=%d, final_top_k=%d, search_type=%s",
            query[:50], top_k, final_top_k, search_type,
        )
        where_clause = filters.to_chroma_where() if filters else None

        candidate_ids: Optional[Set[str]] = None
        if where_clause:
            results = self.collection.get(where=where_clause, limit=10000)
            candidate_ids = set(results["ids"])
            logger.debug("Filtered candidate count: %d", len(candidate_ids))

        vector_results = self._vector_search(
            query, where_clause, top_k, search_type
        )

        # Apply source_path_prefix filter in Python (ChromaDB doesn't support $startswith)
        if filters and filters.source_path_prefix:
            vector_results = [
                r for r in vector_results
                if filters.matches_source_path_prefix(r.chunk.metadata.source_path)
            ]

        bm25_results: List[Tuple[str, float]] = []
        if self.bm25 is not None:
            bm25_results = self.bm25.search(query, top_k, candidate_ids)
            logger.debug("BM25 returned %d results", len(bm25_results))

        if bm25_results and self.bm25 is not None:
            fused = self._reciprocal_rank_fusion(
                vector_results,
                bm25_results,
                final_top_k,
                vector_weight,
                bm25_weight,
                rrf_k,
            )
            logger.info("Hybrid search returned %d results (fused)", len(fused))
            return fused

        logger.info("Vector-only search returned %d results", len(vector_results[:final_top_k]))
        return vector_results[:final_top_k]

    def similarity_search(
        self,
        query: str,
        filters: Optional[MetadataFilter] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        logger.info("Similarity search: query=%s, top_k=%d", query[:50], top_k)
        where_clause = filters.to_chroma_where() if filters else None
        results = self._vector_search(query, where_clause, top_k)

        # Apply source_path_prefix filter in Python (ChromaDB doesn't support $startswith)
        if filters and filters.source_path_prefix:
            results = [
                r for r in results
                if filters.matches_source_path_prefix(r.chunk.metadata.source_path)
            ]

        results = results[:top_k]
        logger.debug("Similarity search returned %d results", len(results))
        return results

    def count(self) -> int:
        c = self.collection.count()
        logger.debug("Vector store count: %d", c)
        return c

    def reset(self) -> None:
        logger.info("Resetting vector store (deleting collection: %s)", self.collection.name)
        self.chroma.delete_collection(self.collection.name)
        self.collection = self.chroma.create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"},
        )
        if self.bm25 is not None:
            logger.debug("Resetting BM25 index")
            self.bm25.reset()
