"""API integration tests via FastAPI TestClient (BM25 RAG mode)."""
from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["index_loaded"] is True


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_optimize_route_happy_path(client):
    r = client.post(
        "/v1/optimize-route",
        json={
            "origin": "Delhi",
            "destination": "Jaipur",
            "vehicle_type": "heavy_truck",
            "payload_kg": 20000,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["recommended_route"]["is_recommended"] is True
    assert body["estimated_carbon_saved_kg"] >= 0
    assert len(body["reasoning_steps"]) >= 4
    assert body["compute_cost"]["cpu_seconds"] >= 0
    # Citations present in at least one reasoning step.
    assert any(step["sources"] for step in body["reasoning_steps"])


def test_optimize_route_validation_error(client):
    r = client.post("/v1/optimize-route", json={"origin": "", "destination": "Jaipur"})
    assert r.status_code == 422


def test_optimize_route_invalid_vehicle(client):
    r = client.post(
        "/v1/optimize-route",
        json={"origin": "A", "destination": "B", "vehicle_type": "spaceship"},
    )
    assert r.status_code == 422


def test_request_id_header_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "test-rid-123"})
    assert r.headers.get("X-Request-ID") == "test-rid-123"


def test_metrics_endpoint(client):
    client.post(
        "/v1/optimize-route",
        json={"origin": "Delhi", "destination": "Mumbai", "vehicle_type": "electric_van"},
    )
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "ecoroute_total_queries" in r.text
    assert "ecoroute_total_carbon_saved_kg" in r.text


def test_knowledge_base_endpoint(client):
    r = client.get("/v1/knowledge-base")
    assert r.status_code == 200
    body = r.json()
    assert body["document_count"] >= 10
    assert "regulation" in body["categories"]


def test_cost_comparison_endpoint(client):
    r = client.get("/v1/cost-comparison", params={"queries": 1000})
    assert r.status_code == 200
    body = r.json()
    assert body["queries"] == 1000
    assert body["per_query"]["cpu_seconds"] >= 0
    assert body["total"]["savings_inr"] > 0
    assert body["total"]["cloud_is_x_times_more_expensive"] > 1
    assert "assumptions" in body


def test_cost_comparison_clamps_queries(client):
    r = client.get("/v1/cost-comparison", params={"queries": 999_999_999})
    assert r.status_code == 200
    assert r.json()["queries"] == 1_000_000


def test_impact_endpoint_accumulates(client):
    before = client.get("/v1/impact").json()["queries_optimized"]
    client.post(
        "/v1/optimize-route",
        json={"origin": "Delhi", "destination": "Jaipur", "vehicle_type": "heavy_truck"},
    )
    after = client.get("/v1/impact").json()
    assert after["queries_optimized"] == before + 1
    assert after["total_carbon_saved_kg"] >= 0


def test_error_envelope_on_unknown_route(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    # FastAPI's default 404 is JSON; ensure it's parseable.
    assert "detail" in r.json()


def test_root_serves_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "EcoRoute AI" in r.text


def test_favicon_not_auth_blocked(client):
    # /favicon.ico must not be a 401 (browser noise); 404 is fine.
    assert client.get("/favicon.ico").status_code != 401
