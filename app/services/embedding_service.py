import httpx
import logging
import asyncio
from typing import List
from app.core.config import settings
import concurrent.futures
from functools import lru_cache
from cachetools import TTLCache
import threading

logger = logging.getLogger(__name__)

# Async HTTP client (shared across requests)
_async_client: httpx.AsyncClient = None


async def get_async_client() -> httpx.AsyncClient:
    """Get or create async HTTP client."""
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(timeout=30.0)
    return _async_client


async def close_async_client():
    """Close async HTTP client."""
    global _async_client
    if _async_client:
        await _async_client.aclose()
        _async_client = None


class OpenRouterEmbeddings:
    """Embeddings using OpenRouter API with query caching."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        # TTL cache for query embeddings (10 min TTL, max 10k queries)
        self._query_cache = TTLCache(maxsize=10000, ttl=600)
        self._cache_lock = threading.Lock()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts using OpenRouter API."""
        if not texts:
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "RAG-API"
                }

                response = await client.post(
                    f"{self.base_url}/embeddings",
                    json={
                        "model": self.model,
                        "input": texts
                    },
                    headers=headers
                )

                if response.status_code != 200:
                    logger.error(f"OpenRouter API error: {response.text}")
                    raise Exception(f"OpenRouter API error: {response.status_code}")

                data = response.json()
                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings

        except Exception as e:
            logger.error(f"Embedding error: {str(e)}")
            raise

    def embed_single(self, text: str) -> List[float]:
        """Embed a single text with query caching (sync wrapper)."""
        # Check cache first
        with self._cache_lock:
            if text in self._query_cache:
                logger.debug(f"Cache hit for query: {text[:50]}")
                return self._query_cache[text]

        # Not in cache, compute and store
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            embedding = asyncio.run(self.embed([text]))[0]
        else:
            embedding = asyncio.create_task(self.embed([text]))

        # Store in cache
        with self._cache_lock:
            self._query_cache[text] = embedding
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts synchronously (for HybridVectorStore)."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._embed_in_thread, texts)
            return future.result(timeout=300)

    def _embed_in_thread(self, texts: List[str]) -> List[List[float]]:
        """Run embedding in a thread with its own event loop."""
        return asyncio.run(self.embed(texts))


class LocalEmbeddings:
    """Local embeddings using sentence-transformers (~5ms per query, in-process)."""

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model)
        self._query_cache = TTLCache(maxsize=10000, ttl=600)
        self._cache_lock = threading.Lock()
        logger.info(f"Loaded local embeddings: {model}")

    async def embed(self, texts: list) -> list:
        """Embed texts locally."""
        if not texts:
            return []
        return self.model.encode(texts, convert_to_tensor=False).tolist()

    def embed_single(self, text: str) -> list:
        """Embed single text with cache."""
        with self._cache_lock:
            if text in self._query_cache:
                logger.debug(f"Cache hit for query: {text[:50]}")
                return self._query_cache[text]

        embedding = self.model.encode(text, convert_to_tensor=False).tolist()
        with self._cache_lock:
            self._query_cache[text] = embedding
        return embedding

    def embed_batch(self, texts: list) -> list:
        """Embed multiple texts."""
        if not texts:
            return []
        return self.model.encode(texts, convert_to_tensor=False).tolist()


def build_embeddings():
    """Build embeddings service (local or OpenRouter)."""
    provider = settings.EMBEDDINGS_PROVIDER.lower()

    if provider == "local":
        logger.info("Using local embeddings (sentence-transformers)")
        return LocalEmbeddings()
    elif provider == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        logger.info(f"Using OpenRouter embeddings: {settings.EMBEDDINGS_MODEL}")
        return OpenRouterEmbeddings(
            api_key=settings.OPENROUTER_API_KEY,
            model=settings.EMBEDDINGS_MODEL
        )
    else:
        raise ValueError(f"Unknown embeddings provider: {provider}")
