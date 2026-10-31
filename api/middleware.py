"""ASGI middleware: request IDs, API-key auth, rate limiting, error envelope.

Order of execution (outermost first):
  1. RequestIDMiddleware   - assigns a correlation id, echoes it in the response
  2. AuthMiddleware        - validates X-API-Key when auth is enabled
  3. RateLimitMiddleware   - per-key token bucket
  4. ErrorEnvelopeMiddleware - converts unhandled exceptions to a JSON envelope
"""
from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.config import get_settings
from core.logger import get_logger, new_request_id, set_request_id

log = get_logger("api.middleware")

# Paths that bypass auth + rate limiting (ops + docs endpoints).
PUBLIC_PATHS = {
    "/",
    "/favicon.ico",
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("X-Request-ID") or new_request_id()
        set_request_id(rid)
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        metrics = getattr(request.app.state, "metrics", None)
        if metrics is not None:
            metrics.record_request(request.url.path, response.status_code)
        log.info(
            "request",
            extra={
                "endpoint": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if request.url.path in PUBLIC_PATHS or not settings.auth_enabled:
            return await call_next(request)

        key = request.headers.get("X-API-Key", "")
        if key not in settings.api_key_list:
            log.warning("auth_failed", extra={"endpoint": request.url.path})
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "unauthorized",
                        "message": "Missing or invalid X-API-Key header",
                        "request_id": getattr(request.state, "request_id", "-"),
                    }
                },
            )
        request.state.api_key = key
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window limiter keyed by API key (or IP)."""

    def __init__(self, app, limit_per_minute: int) -> None:
        super().__init__(app)
        self.limit = limit_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        key = getattr(request.state, "api_key", None) or request.client.host if request.client else "anon"
        now = time.monotonic()
        window = [t for t in self._hits[key] if now - t < 60]
        self._hits[key] = window
        if len(window) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": f"Rate limit exceeded ({self.limit}/min)",
                        "request_id": getattr(request.state, "request_id", "-"),
                    }
                },
                headers={"Retry-After": "60"},
            )
        self._hits[key].append(now)
        return await call_next(request)


class ErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    """Converts unhandled exceptions into a consistent JSON error envelope."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 - intentional top-level catch
            log.error("unhandled_exception", extra={"error": str(exc), "endpoint": request.url.path})
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred",
                        "request_id": getattr(request.state, "request_id", "-"),
                    }
                },
            )


def register_middleware(app) -> None:
    """Register middleware in the correct order (last added runs first)."""
    settings = get_settings()
    # Added last -> runs first
    app.add_middleware(ErrorEnvelopeMiddleware)
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestIDMiddleware)
