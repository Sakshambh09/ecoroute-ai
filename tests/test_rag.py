"""Tests for the RAG service (BM25 path, offline)."""
from __future__ import annotations

from services.rag_service import BM25, _tokenize, chunk_documents


def test_chunk_documents_splits_long_text():
    docs = [{"id": "d1", "title": "T", "category": "c", "region": "r", "content": "word " * 400}]
    chunks = chunk_documents(docs)
    assert len(chunks) > 1
    assert all(c.doc_id == "d1" for c in chunks)


def test_chunk_documents_short_doc_single_chunk():
    docs = [{"id": "d2", "title": "T", "category": "c", "region": "r", "content": "short text"}]
    chunks = chunk_documents(docs)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "d2#0"


def test_tokenize_lowercases_and_strips_punct():
    assert _tokenize("Bharat Stage VI, norms!") == ["bharat", "stage", "vi", "norms"]


def test_bm25_ranks_relevant_doc_first():
    corpus = [
        "electric van zero tailpipe emissions urban delivery",
        "heavy diesel truck idling fuel burn nox emissions",
        "recipe for chocolate cake with vanilla",
    ]
    bm25 = BM25([_tokenize(d) for d in corpus])
    scores = bm25.score(_tokenize("electric van emissions"))
    assert scores[0] > scores[2]
    assert scores[0] > 0


def test_rag_search_returns_relevant_chunks(rag_service):
    outcome = rag_service.search("heavy truck idle fuel burn carbon", top_k=3)
    assert len(outcome.results) >= 1
    # The idle-reduction / heavy-truck chunks should surface.
    top_text = " ".join(r.chunk.text.lower() for r in outcome.results)
    assert "idle" in top_text or "truck" in top_text


def test_rag_search_deterministic(rag_service):
    a = rag_service.search("emission factors medium truck", top_k=3)
    b = rag_service.search("emission factors medium truck", top_k=3)
    assert [r.chunk.chunk_id for r in a.results] == [r.chunk.chunk_id for r in b.results]


def test_rag_metadata(rag_service):
    assert rag_service.document_count >= 10
    assert rag_service.chunk_count >= rag_service.document_count
    assert "regulation" in rag_service.categories
