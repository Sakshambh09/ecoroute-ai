"""Shared fixtures.

The RAG service is exercised in BM25-only (degraded) mode so the test suite
runs without downloading the MiniLM model or building a FAISS index — keeping
CI fast and offline. A separate eval test covers the dense path when the
index is present.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.config import Settings
from services.rag_service import RAGService, chunk_documents

BASE = Path(__file__).resolve().parent.parent


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        api_keys="",  # auth disabled in tests
        index_path=BASE / "data" / "index.faiss",
        chunks_path=BASE / "data" / "chunks.json",
        documents_path=BASE / "data" / "documents.json",
    )


@pytest.fixture()
def rag_service(settings: Settings) -> RAGService:
    """RAG service in BM25-only mode (no model download, no FAISS needed)."""
    rag = RAGService()
    rag.settings = settings
    # Force the BM25-from-source path regardless of persisted artifacts.
    documents = json.loads(settings.documents_path.read_text())
    rag.chunks = chunk_documents(documents)
    from services.rag_service import BM25, _tokenize

    rag.bm25 = BM25([_tokenize(c.text) for c in rag.chunks])
    rag.ready = True
    rag.degraded = True
    return rag


@pytest.fixture()
def client(rag_service: RAGService):
    """FastAPI TestClient with the RAG service injected (BM25 mode).

    The lifespan is intentionally NOT triggered (no `with` block) so the real
    index/model are never loaded — state is set directly, keeping tests fast,
    offline, and deterministic.
    """
    import os
    import tempfile
    from pathlib import Path

    from fastapi.testclient import TestClient

    import core.config as config_mod
    from main import create_app
    from services.agent_service import AgentService
    from services.ledger import CarbonLedger
    from services.metrics import Metrics

    # Force auth off + deterministic settings regardless of any local .env.
    os.environ["API_KEYS"] = ""
    os.environ["INFERENCE_PROVIDER"] = "heuristic"
    config_mod.get_settings.cache_clear()

    app = create_app()
    metrics = Metrics()
    ledger = CarbonLedger(Path(tempfile.mkdtemp()) / "ledger.db")
    app.state.rag_service = rag_service
    app.state.metrics = metrics
    app.state.ledger = ledger
    app.state.agent_service = AgentService(rag=rag_service, metrics=metrics, ledger=ledger)
    return TestClient(app)
