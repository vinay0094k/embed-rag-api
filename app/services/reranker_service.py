import httpx
import logging
import asyncio
from typing import List, Tuple
from app.core.config import settings
from app.services.embedding_service import get_async_client

logger = logging.getLogger(__name__)


class OpenRouterReranker:
    """Reranking using OpenRouter API (async)."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Rerank documents using OpenRouter API.

        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Return top K results

        Returns:
            List of (document, score) tuples sorted by relevance
        """
        if not documents:
            return []

        try:
            with httpx.Client(timeout=30) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "RAG-API"
                }

                # Prepare input for reranker
                # Format: [{"text": "query"}, {"text": "doc1"}, {"text": "doc2"}, ...]
                inputs = [{"text": query}] + [{"text": doc} for doc in documents]

                response = client.post(
                    f"{self.base_url}/embeddings",
                    json={
                        "model": self.model,
                        "input": inputs
                    },
                    headers=headers
                )

                if response.status_code != 200:
                    logger.error(f"OpenRouter rerank error: {response.text}")
                    raise Exception(f"OpenRouter API error: {response.status_code}")

                data = response.json()

                # Calculate relevance scores (cosine similarity with query embedding)
                query_embedding = data["data"][0]["embedding"]
                scores = []

                for i, doc in enumerate(documents):
                    doc_embedding = data["data"][i + 1]["embedding"]
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(query_embedding, doc_embedding)
                    scores.append((doc, similarity))

                # Sort by score (descending) and return top_k
                scores.sort(key=lambda x: x[1], reverse=True)
                return scores[:top_k]

        except Exception as e:
            logger.error(f"Reranking error: {str(e)}")
            raise

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()


class LocalReranker:
    """Local reranking using cross-encoder (fallback)."""

    def __init__(self):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Rerank documents locally."""
        scores = self.model.predict(
            [[query, doc] for doc in documents]
        )

        ranked = list(zip(documents, scores))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


def build_reranker():
    """Build reranker service based on configuration."""
    if settings.EMBEDDINGS_PROVIDER == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not set, reranking disabled")
            return None

        logger.info("Using OpenRouter reranker: nvidia/llama-nemotron-rerank-vl-1b-v2")
        return OpenRouterReranker(
            api_key=settings.OPENROUTER_API_KEY,
            model="nvidia/llama-nemotron-rerank-vl-1b-v2"
        )
    else:
        logger.info("Using local reranker: cross-encoder/ms-marco-MiniLM-L-12-v2")
        return LocalReranker()
