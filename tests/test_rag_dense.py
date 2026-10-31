"""Tests for the dense (FAISS + MiniLM) hybrid path.

These require the persisted index (built via `make index`) and the embedding
model. They skip automatically when the index is absent so the fast offline
suite still runs in CI without the ML stack.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.rag_service import RAGService

BASE = Path(__file__).resolve().parent.parent
INDEX = BASE / "data" / "index.faiss"
VECTORS = BASE / "data" / "index.vectors.npy"

pytestmark = pytest.mark.skipif(
    not (INDEX.exists() and VECTORS.exists()),
    reason="dense index not built (run: make index)",
)


@pytest.fixture(scope="module")
def dense_rag() -> RAGService:
    rag = RAGService()
    rag.load()
    assert rag.ready
    assert rag.degraded is False, "expected the dense (non-degraded) path"
    return rag


def test_dense_path_not_degraded(dense_rag: RAGService):
    assert dense_rag._index is not None
    assert dense_rag._embeddings is not None
    assert dense_rag._embeddings.shape[0] == dense_rag.chunk_count


def test_dense_search_returns_dense_rank(dense_rag: RAGService):
    out = dense_rag.search("heavy truck idling fuel burn", top_k=3)
    assert out.degraded is False
    assert len(out.results) >= 1
    # At least the top result should have a dense rank (dense channel active).
    assert out.results[0].dense_rank is not None


def test_dense_search_semantic_match(dense_rag: RAGService):
    # Semantic (not just keyword) match: paraphrase should still retrieve the doc.
    out = dense_rag.search("how much carbon does a diesel lorry emit per tonne", top_k=3)
    top_docs = {r.chunk.doc_id for r in out.results}
    assert any(
        d in top_docs
        for d in ("doc-heavy-truck-emission-factor", "doc-carbon-accounting", "doc-medium-truck-emission-factor")
    ), f"semantic retrieval failed, got {top_docs}"


def test_warmup_is_noop_without_index():
    rag = RAGService()
    # No index loaded -> warmup must not raise.
    rag.warmup()
