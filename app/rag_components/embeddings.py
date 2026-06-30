import asyncio
import logging
import os
import time
from collections import OrderedDict
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Query embedding LRU cache (shared across all OpenRouterEmbeddings instances) ──
_QUERY_CACHE_MAX = 512
_query_cache: OrderedDict = OrderedDict()


def _cache_get(text: str) -> Optional[List[float]]:
    if text in _query_cache:
        _query_cache.move_to_end(text)
        return _query_cache[text]
    return None


def _cache_put(text: str, vector: List[float]) -> None:
    _query_cache[text] = vector
    if len(_query_cache) > _QUERY_CACHE_MAX:
        _query_cache.popitem(last=False)


class LocalEmbeddings:
    """Legacy MLX embedding class — kept for API compatibility, delegates to DefaultEmbeddings."""

    def __init__(self, *args, **kwargs):
        logger.warning("LocalEmbeddings is deprecated, use DefaultEmbeddings")
        self._inner = DefaultEmbeddings(*args, **kwargs)

    def embed(self, texts):
        return self._inner.embed(texts)

    async def embed_async(self, texts):
        return await self._inner.embed_async(texts)

    @property
    def dimension(self):
        return self._inner.dimension


class DefaultEmbeddings:
    """Local ONNX-based embeddings using ChromaDB's built-in MiniLM-L6-v2 model."""

    def __init__(self, batch_size: int = 100, **kwargs):
        self.batch_size = batch_size
        self._ef = None

    def _get_ef(self):
        if self._ef is None:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            logger.info("Loading ONNX MiniLM-L6-v2 embedding model (first use downloads ~80MB)")
            self._ef = ONNXMiniLM_L6_V2()
            logger.info("ONNX embedding model loaded")
        return self._ef

    def embed(self, texts: List[str]) -> List[List[float]]:
        logger.info("Embedding %d texts (batch_size=%d)", len(texts), self.batch_size)
        ef = self._get_ef()
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        results: List[List[float]] = []
        for i, batch in enumerate(batches):
            logger.debug("Batch %d/%d: %d texts", i + 1, len(batches), len(batch))
            results.extend(ef(batch))
        logger.info("Embedding complete: %d vectors", len(results))
        return results

    async def embed_async(self, texts: List[str]) -> List[List[float]]:
        return self.embed(texts)

    @property
    def dimension(self) -> Optional[int]:
        return 384  # all-MiniLM-L6-v2


class OpenRouterEmbeddings:
    """OpenRouter-hosted embeddings via OpenAI-compatible API.

    Improvements over naive implementation:
    - Retry with exponential backoff on transient failures
    - LRU cache for query embeddings (avoids repeated API calls)
    - Concurrent async batches during indexing (semaphore-limited)
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    # Max concurrent async batch requests — free tier is rate-limited
    _ASYNC_CONCURRENCY = 4
    # Retry settings — 2 attempts max; SDK-level retries are disabled
    _MAX_RETRIES = 2
    _RETRY_BASE_DELAY = 1.0  # seconds, doubles each attempt

    def __init__(
        self,
        model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        api_key: Optional[str] = None,
        batch_size: int = 16,
        dimension: int = 2048,
        **kwargs,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required: set OPENROUTER_API_KEY env var "
                "or embeddings.openrouter_api_key in config"
            )
        self.batch_size = batch_size
        self._dimension = dimension
        self._client = None
        self._async_client = None

    # Per-request timeout in seconds. OpenRouter free tier can be slow but
    # hanging indefinitely is worse than a fast failure + retry.
    _REQUEST_TIMEOUT = 30.0

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.OPENROUTER_BASE_URL,
                timeout=self._REQUEST_TIMEOUT,
                max_retries=0,  # our _call_api handles retries
            )
        return self._client

    def _get_async_client(self):
        if self._async_client is None:
            from openai import AsyncOpenAI
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.OPENROUTER_BASE_URL,
                timeout=self._REQUEST_TIMEOUT,
                max_retries=0,  # our _call_api_async handles retries
            )
        return self._async_client

    # ── Retry helpers ──────────────────────────────────────────────────────────

    def _call_api(self, client, batch: List[str], input_type: str) -> List[List[float]]:
        last_exc = None
        for attempt in range(self._MAX_RETRIES):
            try:
                response = client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float",
                    extra_body={"input_type": input_type, "truncate": "END"},
                )
                if not response.data:
                    raise RuntimeError(
                        f"OpenRouter returned empty data (model={self.model}, "
                        f"batch={len(batch)}, input_type={input_type})"
                    )
                embeddings = [item.embedding for item in response.data]
                if any(e is None for e in embeddings):
                    raise RuntimeError(f"OpenRouter returned null embeddings (model={self.model})")
                return embeddings
            except Exception as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES - 1:
                    delay = self._RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Embed attempt %d/%d failed (%s), retrying in %.1fs",
                        attempt + 1, self._MAX_RETRIES, exc, delay,
                    )
                    time.sleep(delay)
        raise RuntimeError(
            f"Embedding failed after {self._MAX_RETRIES} attempts"
        ) from last_exc

    async def _call_api_async(
        self, client, batch: List[str], input_type: str
    ) -> List[List[float]]:
        last_exc = None
        for attempt in range(self._MAX_RETRIES):
            try:
                response = await client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float",
                    extra_body={"input_type": input_type, "truncate": "END"},
                )
                if not response.data:
                    raise RuntimeError(
                        f"OpenRouter returned empty data (model={self.model}, "
                        f"batch={len(batch)}, input_type={input_type})"
                    )
                embeddings = [item.embedding for item in response.data]
                if any(e is None for e in embeddings):
                    raise RuntimeError(f"OpenRouter returned null embeddings (model={self.model})")
                return embeddings
            except Exception as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES - 1:
                    delay = self._RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Async embed attempt %d/%d failed (%s), retrying in %.1fs",
                        attempt + 1, self._MAX_RETRIES, exc, delay,
                    )
                    await asyncio.sleep(delay)
        raise RuntimeError(
            f"Async embedding failed after {self._MAX_RETRIES} attempts"
        ) from last_exc

    # ── Public API ─────────────────────────────────────────────────────────────

    def embed(self, texts: List[str], input_type: str = "passage") -> List[List[float]]:
        logger.info(
            "OpenRouter embedding %d texts via %s (batch_size=%d, input_type=%s)",
            len(texts), self.model, self.batch_size, input_type,
        )
        client = self._get_client()
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        results: List[List[float]] = []
        for i, batch in enumerate(batches):
            logger.debug("Batch %d/%d: %d texts", i + 1, len(batches), len(batch))
            results.extend(self._call_api(client, batch, input_type))
        logger.info("OpenRouter embedding complete: %d vectors", len(results))
        return results

    def embed_query(self, texts: List[str]) -> List[List[float]]:
        """Query-side embedding with LRU cache — skips API for repeated queries."""
        results: List[List[float]] = []
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        for i, text in enumerate(texts):
            cached = _cache_get(text)
            if cached is not None:
                results.append(cached)
            else:
                results.append(None)  # placeholder
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            if len(uncached_texts) < len(texts):
                logger.debug(
                    "Query cache: %d hits, %d misses",
                    len(texts) - len(uncached_texts), len(uncached_texts),
                )
            fresh = self.embed(uncached_texts, input_type="query")
            for idx, text, vector in zip(uncached_indices, uncached_texts, fresh):
                _cache_put(text, vector)
                results[idx] = vector

        return results

    async def embed_async(
        self, texts: List[str], input_type: str = "passage"
    ) -> List[List[float]]:
        """Async embedding with concurrent batches (semaphore-limited to avoid rate limits)."""
        logger.info(
            "OpenRouter async embedding %d texts via %s (batch_size=%d, input_type=%s, concurrency=%d)",
            len(texts), self.model, self.batch_size, input_type, self._ASYNC_CONCURRENCY,
        )
        client = self._get_async_client()
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        semaphore = asyncio.Semaphore(self._ASYNC_CONCURRENCY)

        async def fetch_batch(batch: List[str]) -> List[List[float]]:
            async with semaphore:
                return await self._call_api_async(client, batch, input_type)

        batch_results = await asyncio.gather(*[fetch_batch(b) for b in batches])

        results: List[List[float]] = []
        for batch_embs in batch_results:
            results.extend(batch_embs)

        logger.info("OpenRouter async embedding complete: %d vectors", len(results))
        return results

    @property
    def dimension(self) -> int:
        return self._dimension


def build_embeddings(provider: str = "chroma_default", **kwargs):
    """Factory: returns the appropriate embeddings instance based on provider name."""
    if provider == "openrouter":
        return OpenRouterEmbeddings(**kwargs)
    return DefaultEmbeddings(**kwargs)
