"""Query expansion service using OpenRouter chat API."""

import asyncio
import logging
from typing import List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryExpansionService:
    """Generate search query variants using LLM."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    REQUEST_TIMEOUT = 10.0

    @staticmethod
    async def generate_variants(
        query: str, num_variants: int = 3, timeout: float = 5.0
    ) -> List[str]:
        """Generate query variants using OpenRouter chat API.

        Returns empty list on timeout or error (graceful degradation).
        """
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not set, skipping query expansion")
            return []

        prompt = f"""Given the search query: "{query}"
Generate {num_variants} different search queries that capture different
aspects or phrasings of the original query.
Return only the queries, one per line, without numbering or bullet points.
Each query must be self-contained and searchable."""

        try:
            async with httpx.AsyncClient(timeout=QueryExpansionService.REQUEST_TIMEOUT) as client:
                response = await asyncio.wait_for(
                    client.post(
                        f"{QueryExpansionService.OPENROUTER_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": settings.QUERY_EXPANSION_MODEL,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7,
                            "max_tokens": 200,
                        },
                    ),
                    timeout=timeout,
                )

                if response.status_code != 200:
                    logger.warning(
                        f"Query expansion API error: {response.status_code} - {response.text}"
                    )
                    return []

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                variants = [line.strip() for line in content.split("\n") if line.strip()]
                return variants[:num_variants]

        except asyncio.TimeoutError:
            logger.warning(f"Query expansion timed out after {timeout}s, using original query only")
            return []
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}, using original query only")
            return []
