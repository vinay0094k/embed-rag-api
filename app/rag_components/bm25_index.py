import logging
import math
import pickle
import re
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Set, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from app.rag_components.config import BM25Config
from app.rag_components.models import DocumentChunk

logger = logging.getLogger(__name__)

class RobustBM25(BM25Okapi):
    def _calc_idf(self, nd):
        idf_sum = 0
        negative_idfs = []
        for word, freq in nd.items():
            idf = math.log(self.corpus_size - freq + 0.5) - math.log(freq + 0.5)
            self.idf[word] = idf
            idf_sum += idf
            if idf < 0:
                negative_idfs.append(word)
        self.average_idf = idf_sum / max(len(self.idf), 1)

        eps = max(self.epsilon * self.average_idf, 1e-6)
        for word in negative_idfs:
            self.idf[word] = eps


class BM25Index:
    _CACHE_MAX = 10000

    def __init__(self, config: Optional[BM25Config] = None):
        self.config = config or BM25Config()
        self.index: Optional[RobustBM25] = None
        self.doc_ids: List[str] = []
        self.tokenized_docs: List[List[str]] = []
        self._token_cache: OrderedDict = OrderedDict()
        self._load()

    def _tokenize(self, text: str) -> List[str]:
        if text in self._token_cache:
            self._token_cache.move_to_end(text)
            return self._token_cache[text]
        tokens = re.findall(r"\b\w+\b", text.lower())
        tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]
        self._token_cache[text] = tokens
        if len(self._token_cache) > self._CACHE_MAX:
            self._token_cache.popitem(last=False)  # evict oldest entry
        return tokens

    def add_documents(self, chunks: List[DocumentChunk]) -> None:
        if not chunks:
            logger.debug("add_documents called with empty list")
            return

        new_tokenized: List[List[str]] = []
        new_ids: List[str] = []

        for chunk in chunks:
            tokens = self._tokenize(chunk.content)
            if not tokens:
                continue
            new_tokenized.append(tokens)
            new_ids.append(chunk.id)

        if not new_tokenized:
            logger.debug("No tokenizable content in %d chunks", len(chunks))
            return

        logger.info("Adding %d documents to BM25 index", len(new_ids))
        if self.index is None:
            self.tokenized_docs = new_tokenized
            self.doc_ids = new_ids
        else:
            existing_ids = set(self.doc_ids)
            added = 0
            for doc_id, tokens in zip(new_ids, new_tokenized):
                if doc_id not in existing_ids:
                    self.doc_ids.append(doc_id)
                    self.tokenized_docs.append(tokens)
                    existing_ids.add(doc_id)
                    added += 1
            logger.debug("Added %d new docs to existing BM25 index", added)

        self._rebuild()
        self._persist()

    def _rebuild(self) -> None:
        if not self.tokenized_docs:
            self.index = None
            return
        self.index = RobustBM25(
            self.tokenized_docs,
            k1=self.config.k1,
            b=self.config.b,
        )

    def search(
        self,
        query: str,
        top_k: int = 20,
        filter_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[str, float]]:
        if self.index is None or not self.doc_ids:
            logger.debug("BM25 search skipped: no index or empty doc list")
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            logger.debug("BM25 search skipped: no query tokens")
            return []

        scores = self.index.get_scores(query_tokens)

        results: List[Tuple[str, float]] = []
        for doc_id, score in zip(self.doc_ids, scores):
            if score <= 0:
                continue
            if filter_ids is not None and doc_id not in filter_ids:
                continue
            results.append((doc_id, float(score)))

        results.sort(key=lambda x: x[1], reverse=True)
        top_results = results[:top_k]
        logger.debug("BM25 search: query=%s, top_k=%d, results=%d", query[:30], top_k, len(top_results))
        return top_results

    def suggest_terms(self, prefix: str, top_k: int = 10) -> List[str]:
        """Get term suggestions based on prefix (case-insensitive)."""
        if self.index is None or not self.index.idf:
            logger.debug("BM25 suggest skipped: no index")
            return []

        prefix_lower = prefix.lower().strip()
        if not prefix_lower:
            return []

        # Find terms matching the prefix, ranked by IDF (importance)
        matching_terms = [
            (term, self.index.idf.get(term, 0))
            for term in self.index.idf.keys()
            if term.startswith(prefix_lower)
        ]

        # Sort by IDF descending (most important terms first)
        matching_terms.sort(key=lambda x: x[1], reverse=True)
        suggestions = [term for term, _ in matching_terms[:top_k]]
        logger.debug("BM25 suggest: prefix=%s, suggestions=%d", prefix[:20], len(suggestions))
        return suggestions

    def remove_documents(self, doc_ids: Set[str]) -> None:
        if not doc_ids or not self.doc_ids:
            logger.debug("remove_documents: nothing to remove")
            return

        logger.info("Removing %d documents from BM25 index", len(doc_ids))
        keep_indices = [
            i for i, doc_id in enumerate(self.doc_ids) if doc_id not in doc_ids
        ]

        self.doc_ids = [self.doc_ids[i] for i in keep_indices]
        self.tokenized_docs = [self.tokenized_docs[i] for i in keep_indices]

        self._rebuild()
        self._persist()

    def reset(self) -> None:
        logger.info("Resetting BM25 index")
        self.index = None
        self.doc_ids = []
        self.tokenized_docs = []
        self._clear_persist()

    @property
    def size(self) -> int:
        return len(self.doc_ids)

    def _persist_path(self) -> Path:
        return Path(self.config.index_path)

    def _persist(self) -> None:
        path = self._persist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "doc_ids": self.doc_ids,
            "tokenized_docs": self.tokenized_docs,
            "k1": self.config.k1,
            "b": self.config.b,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.debug("Persisted BM25 index: %s (%d docs)", path, len(self.doc_ids))

    def _load(self) -> None:
        path = self._persist_path()
        if not path.exists():
            logger.debug("No BM25 index file at %s", path)
            return

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.doc_ids = data.get("doc_ids", [])
            self.tokenized_docs = data.get("tokenized_docs", [])
            k1 = data.get("k1", self.config.k1)
            b = data.get("b", self.config.b)
            if self.tokenized_docs:
                self.index = RobustBM25(
                    self.tokenized_docs, k1=k1, b=b
                )
            logger.info("Loaded BM25 index: %s (%d docs)", path, len(self.doc_ids))
        except Exception as e:
            logger.warning("Failed to load BM25 index from %s: %s", path, e)
            self.doc_ids = []
            self.tokenized_docs = []
            self.index = None

    def _clear_persist(self) -> None:
        path = self._persist_path()
        if path.exists():
            path.unlink()
            logger.debug("Removed BM25 index file: %s", path)
