"""Unit/integration tests for middleware: auth, rate limit, request-id, errors."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

import core.config as config_mod
from main import create_app


def _client_with_auth(api_keys: str, rate_limit: int = 60) -> TestClient:
    os.environ["API_KEYS"] = api_keys
    os.environ["RATE_LIMIT_PER_MINUTE"] = str(rate_limit)
    config_mod.get_settings.cache_clear()
    app = create_app()
    # Minimal state so /health works without the real services.
    app.state.rag_service = None
    app.state.agent_service = None
    app.state.metrics = None
    return TestClient(app)


def test_auth_required_when_keys_configured():
    c = _client_with_auth("secret-1")
    # Public path works without a key.
    assert c.get("/health").status_code == 200
    # Protected path rejects missing key.
    assert c.get("/v1/knowledge-base").status_code == 401
    # Protected path rejects wrong key.
    assert c.get("/v1/knowledge-base", headers={"X-API-Key": "nope"}).status_code == 401
    # Correct key passes auth (503 because KB not loaded, but NOT 401).
    assert c.get("/v1/knowledge-base", headers={"X-API-Key": "secret-1"}).status_code == 503


def test_auth_disabled_when_no_keys():
    c = _client_with_auth("")
    # No auth -> protected path reachable (503, not 401).
    assert c.get("/v1/knowledge-base").status_code == 503


def test_request_id_generated_when_absent():
    c = _client_with_auth("")
    r = c.get("/health")
    assert r.headers.get("X-Request-ID"), "expected a generated request id"
    assert r.headers.get("X-Process-Time-Ms")


def test_request_id_echoed_when_provided():
    c = _client_with_auth("")
    r = c.get("/health", headers={"X-Request-ID": "my-rid-999"})
    assert r.headers.get("X-Request-ID") == "my-rid-999"


def test_rate_limit_enforced():
    c = _client_with_auth("k", rate_limit=3)
    codes = [
        c.get("/v1/knowledge-base", headers={"X-API-Key": "k"}).status_code for _ in range(5)
    ]
    assert codes.count(429) == 2  # first 3 pass auth (503), last 2 rate-limited
    assert 429 in codes


def test_error_envelope_on_unhandled_exception():
    # A raw (non-HTTP) exception must become a JSON error envelope, not a traceback.
    from fastapi import FastAPI

    from api.middleware import ErrorEnvelopeMiddleware

    app = FastAPI()
    app.add_middleware(ErrorEnvelopeMiddleware)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert "request_id" in body["error"]
