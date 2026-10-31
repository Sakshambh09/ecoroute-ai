"""Local RAG engine: CPU-optimized, privacy-first retrieval.

Design:
- Dense retrieval: sentence-transformers MiniLM embeddings + FAISS (cosine via
  inner product on L2-normalized vectors).
- Sparse retrieval: lightweight in-process BM25 (no extra dependency).
- Fusion: Reciprocal Rank Fusion (RRF) merges both rankings.
- Persistence: the FAISS index + chunk metadata are saved to disk so the
  server never re-embeds documents at boot (fast, deterministic startup).
- Degradation: if the embedding model cannot load, the service falls back to
  BM25-only and flags `degraded=True` on results.
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.config import get_settings
from core.logger import get_logger

log = get_logger("services.rag")

CHUNK_SIZE = 600  # chars per chunk
CHUNK_OVERLAP = 100
_RRF_K = 60  # standard RRF constant


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    category: str
    region: str
    text: str


@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    dense_rank: int | None
    sparse_rank: int | None


@dataclass
class SearchOutcome:
    results: list[SearchResult]
    degraded: bool = False
    latency_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25:
    """Minimal Okapi BM25 over a list of tokenized documents."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = corpus_tokens
        self.n = len(corpus_tokens)
        self.avgdl = (sum(len(d) for d in corpus_tokens) / self.n) if self.n else 0.0
        self.df: dict[str, int] = {}
        for doc in corpus_tokens:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.n
        for term in query_tokens:
            idf = self._idf(term)
            for i, doc in enumerate(self.corpus):
                tf = doc.count(term)
                if tf:
                    dl = len(doc)
                    scores[i] += idf * (tf * (self.k1 + 1)) / (
                        tf + self.k1 * (1 - self.b + self.b * (dl / self.avgdl if self.avgdl else 1))
                    )
        return scores


def chunk_documents(documents: list[dict[str, Any]]) -> list[Chunk]:
    """Split documents into overlapping chunks for retrieval granularity."""
    chunks: list[Chunk] = []
    for doc in documents:
        text = doc["content"].strip()
        doc_id = doc["id"]
        if len(text) <= CHUNK_SIZE:
            chunks.append(
                Chunk(f"{doc_id}#0", doc_id, doc["title"], doc["category"], doc["region"], text)
            )
            continue
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            # Prefer breaking at a sentence boundary when possible.
            if end < len(text):
                space = text.rfind(" ", start + CHUNK_SIZE // 2, end)
                if space > start:
                    end = space
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    Chunk(f"{doc_id}#{idx}", doc_id, doc["title"], doc["category"], doc["region"], piece)
                )
            idx += 1
            start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


class RAGService:
    """Loads the persisted index at startup and serves hybrid searches."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.chunks: list[Chunk] = []
        self.bm25: BM25 | None = None
        self._index: Any = None  # faiss index
        self._embeddings: np.ndarray | None = None
        self._model: Any = None
        self.ready = False
        self.degraded = False
        self.index_built_at: str | None = None
        self.embedding_model_name = self.settings.embedding_model
        self._meta_path = self.settings.index_path.with_suffix(".meta.json")
        self._vectors_path = self.settings.index_path.with_suffix(".vectors.npy")

    def load(self) -> None:
        """Load persisted index + chunks. Falls back to BM25-only if unavailable."""
        t0 = time.perf_counter()
        if not self.settings.chunks_path.exists():
            log.warning("chunks_not_found", extra={"path": str(self.settings.chunks_path)})
            self._load_bm25_only()
            return
        self.chunks = [Chunk(**c) for c in json.loads(self.settings.chunks_path.read_text())]
        self.bm25 = BM25([_tokenize(c.text) for c in self.chunks])
        if self._meta_path.exists():
            self.index_built_at = json.loads(self._meta_path.read_text()).get("built_at")

        if self.settings.index_path.exists() and self._vectors_path.exists():
            try:
                import faiss

                self._index = faiss.read_index(str(self.settings.index_path))
                self._embeddings = np.load(self._vectors_path).astype("float32")
                if self._embeddings.shape[0] != len(self.chunks):
                    raise ValueError("vector/chunk count mismatch")
                self.ready = True
                log.info(
                    "rag_loaded",
                    extra={"chunks": len(self.chunks), "ms": round((time.perf_counter() - t0) * 1000, 1)},
                )
                return
            except Exception as exc:  # noqa: BLE001
                log.error("faiss_load_failed", extra={"error": str(exc)})

        # No usable dense index -> degraded BM25-only mode.
        self.degraded = True
        self.ready = True
        log.warning("rag_degraded_bm25_only", extra={"chunks": len(self.chunks)})

    def _load_bm25_only(self) -> None:
        """Last-resort path: build BM25 straight from documents.json."""
        docs_path = self.settings.documents_path
        if not docs_path.exists():
            log.error("documents_not_found", extra={"path": str(docs_path)})
            return
        documents = json.loads(docs_path.read_text())
        self.chunks = chunk_documents(documents)
        self.bm25 = BM25([_tokenize(c.text) for c in self.chunks])
        self.degraded = True
        self.ready = True
        log.warning("rag_bm25_from_source", extra={"chunks": len(self.chunks)})

    def warmup(self) -> None:
        """Pre-load the embedding model and run a dummy encode.

        Called at startup so the first real query does not pay the ~10s model
        load cost. Safe to call when the dense path is unavailable (no-op).
        """
        if self._index is None:
            return
        t0 = time.perf_counter()
        self._embed_query("warmup")
        log.info(
            "embed_model_warmed",
            extra={"ms": round((time.perf_counter() - t0) * 1000, 1)},
        )

    def search(self, query: str, top_k: int | None = None) -> SearchOutcome:
        """Hybrid dense+sparse search with RRF fusion. Deterministic."""
        t0 = time.perf_counter()
        top_k = top_k or self.settings.rag_top_k
        if not self.ready:
            return SearchOutcome(results=[], degraded=True, latency_ms=0.0)

        query_tokens = _tokenize(query)
        sparse_scores = self.bm25.score(query_tokens) if self.bm25 else [0.0] * len(self.chunks)
        sparse_order = sorted(range(len(self.chunks)), key=lambda i: -sparse_scores[i])
        sparse_rank = {idx: rank for rank, idx in enumerate(sparse_order)}

        dense_rank: dict[int, int] = {}
        if self._index is not None and self._embeddings is not None:
            qvec = self._embed_query(query)
            if qvec is not None:
                k = min(max(top_k * 3, 10), len(self.chunks))
                scores, idxs = self._index.search(qvec, k)
                for rank, (s, i) in enumerate(zip(scores[0], idxs[0], strict=False)):
                    if s > 0:
                        dense_rank[int(i)] = rank

        # Reciprocal Rank Fusion
        fused: dict[int, float] = {}
        all_ids = set(sparse_rank) | set(dense_rank)
        for i in all_ids:
            score = 0.0
            if i in sparse_rank:
                score += 1.0 / (_RRF_K + sparse_rank[i] + 1)
            if i in dense_rank:
                score += 1.0 / (_RRF_K + dense_rank[i] + 1)
            fused[i] = score

        top = sorted(fused, key=lambda i: (-fused[i], i))[:top_k]
        results = [
            SearchResult(
                chunk=self.chunks[i],
                score=fused[i],
                dense_rank=dense_rank.get(i),
                sparse_rank=sparse_rank.get(i),
            )
            for i in top
            if fused[i] > 0
        ]
        return SearchOutcome(
            results=results,
            degraded=self.degraded,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    def _embed_query(self, query: str) -> np.ndarray | None:
        """Embed a query using the cached model, or a persisted query encoder.

        To keep boot light we lazily load the model on first query; if it
        fails we return None and rely on the sparse channel.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.settings.embedding_model)
            except Exception as exc:  # noqa: BLE001
                log.error("embed_model_load_failed", extra={"error": str(exc)})
                self.degraded = True
                return None
        vec = self._model.encode(query, normalize_embeddings=True).astype("float32")
        return vec.reshape(1, -1)

    @property
    def document_count(self) -> int:
        return len({c.doc_id for c in self.chunks})

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def categories(self) -> list[str]:
        return sorted({c.category for c in self.chunks})
