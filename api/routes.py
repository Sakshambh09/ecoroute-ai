"""API endpoints.

Services are accessed via `request.app.state` (populated in the FastAPI
lifespan) so this module has no import-time dependency on heavy models.
CPU-bound work uses sync `def` handlers so FastAPI runs them in a threadpool
and never blocks the event loop.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from api.schemas import (
    HealthResponse,
    KnowledgeBaseInfo,
    QueryRequest,
    QueryResponse,
)
from core.config import get_settings
from core.logger import get_logger

log = get_logger("api.routes")
router = APIRouter()

APP_VERSION = "1.0.0"


@router.post("/v1/optimize-route", response_model=QueryResponse)
def optimize_route(payload: QueryRequest, request: Request) -> QueryResponse:
    """Core endpoint: retrieve regulatory context, compute routes, return reasoning."""
    agent = request.app.state.agent_service
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent service not initialized")
    return agent.handle_query(payload, request_id=request.state.request_id)


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Liveness probe: process is up."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        index_loaded=bool(request.app.state.rag_service and request.app.state.rag_service.ready),
        inference_provider=settings.inference_provider,
        auth_enabled=settings.auth_enabled,
    )


@router.get("/ready", response_model=HealthResponse)
def ready(request: Request) -> HealthResponse:
    """Readiness probe: verifies the RAG index is actually loaded."""
    settings = get_settings()
    rag = request.app.state.rag_service
    index_loaded = bool(rag and rag.ready)
    resp = HealthResponse(
        status="ready" if index_loaded else "not_ready",
        version=APP_VERSION,
        index_loaded=index_loaded,
        inference_provider=settings.inference_provider,
        auth_enabled=settings.auth_enabled,
    )
    if not index_loaded:
        raise HTTPException(status_code=503, detail=resp)
    return resp


@router.get("/v1/cost-comparison")
def cost_comparison(request: Request, queries: int = 1000) -> dict:
    """Dramatic CPU-vs-cloud cost analysis (the sustainability money shot).

    Projects the cost of `queries` requests on the local CPU stack vs a cloud
    LLM API, using a real measured per-query CPU time.
    """
    agent = request.app.state.agent_service
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent service not initialized")
    queries = max(1, min(queries, 1_000_000))
    return agent.cost_comparison(queries=queries)


@router.get("/v1/impact")
def impact(request: Request) -> dict:
    """Durable cumulative impact from the persistent ledger (survives restarts)."""
    ledger = request.app.state.ledger
    if ledger is None:
        raise HTTPException(status_code=503, detail="Ledger not initialized")
    count, total_kg = ledger.totals()
    return {
        "queries_optimized": count,
        "total_carbon_saved_kg": round(total_kg, 2),
        "note": "Durable ledger (SQLite) — cumulative since first run, survives restarts.",
    }


@router.get("/v1/knowledge-base", response_model=KnowledgeBaseInfo)
def knowledge_base(request: Request) -> KnowledgeBaseInfo:
    """Inspect the local knowledge base: proves the RAG is real and auditable."""
    rag = request.app.state.rag_service
    if rag is None or not rag.ready:
        raise HTTPException(status_code=503, detail="Knowledge base not loaded")
    return KnowledgeBaseInfo(
        document_count=rag.document_count,
        chunk_count=rag.chunk_count,
        categories=rag.categories,
        index_built_at=rag.index_built_at,
        embedding_model=rag.embedding_model_name,
    )


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request) -> str:
    """Prometheus-format metrics endpoint (text/plain for scrapers)."""
    m = request.app.state.metrics
    if m is None:
        raise HTTPException(status_code=503, detail="Metrics not initialized")
    return m.render()
