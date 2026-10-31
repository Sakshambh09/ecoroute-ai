"""EcoRoute AI — application entry point.

Wires the RAG engine, inference provider, agent orchestrator, and metrics
together in the FastAPI lifespan, registers middleware, and exposes the API.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.middleware import register_middleware
from api.routes import router
from core.config import get_settings
from core.inference import get_provider
from core.logger import get_logger
from services.agent_service import AgentService
from services.ledger import CarbonLedger
from services.metrics import Metrics
from services.rag_service import RAGService

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info(
        "startup_begin",
        extra={"provider": settings.inference_provider, "model": settings.embedding_model},
    )

    # 1. RAG engine (loads persisted index; degrades to BM25 if absent)
    rag = RAGService()
    rag.load()
    # Pre-load the embedding model so the first query is fast (not ~10s).
    rag.warmup()

    # 2. Metrics + persistent ledger + inference provider + agent
    metrics = Metrics()
    ledger = CarbonLedger(settings.ledger_path)
    provider = get_provider(settings.inference_provider)
    agent = AgentService(rag=rag, provider=provider, metrics=metrics, ledger=ledger)

    app.state.rag_service = rag
    app.state.agent_service = agent
    app.state.metrics = metrics
    app.state.ledger = ledger

    log.info(
        "startup_complete",
        extra={
            "index_loaded": rag.ready,
            "degraded": rag.degraded,
            "chunks": rag.chunk_count,
        },
    )
    yield
    app.state.ledger.close()
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EcoRoute AI",
        version="1.0.0",
        description=(
            "Privacy-first, CPU-native sustainable route optimization with local RAG. "
            "Retrieves emission guidelines, computes carbon per route, and returns "
            "citation-backed reasoning — all on-device."
        ),
        lifespan=lifespan,
    )

    # CORS: explicit origins only (no wildcard in production).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    register_middleware(app)
    app.include_router(router)

    # Web UI: mounted last so the API routes above take precedence.
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="ui")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run("main:app", host=s.host, port=s.port, reload=s.debug)
