"""Unit tests for core modules: config, logger, metrics, inference."""
from __future__ import annotations

import json
import logging

import pytest

from core.config import Settings
from core.inference import HeuristicProvider, KompactProvider, get_provider
from core.logger import JsonFormatter, get_logger, new_request_id, set_request_id
from services.metrics import Metrics


def test_settings_defaults():
    s = Settings(api_keys="")
    assert s.auth_enabled is False
    assert s.inference_provider == "heuristic"
    assert s.rag_top_k == 3


def test_settings_api_key_parsing():
    s = Settings(api_keys="a, b ,c,,")
    assert s.api_key_list == ["a", "b", "c"]
    assert s.auth_enabled is True


def test_settings_invalid_provider_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(inference_provider="bogus")


def test_request_id_roundtrip():
    rid = new_request_id()
    set_request_id(rid)
    from core.logger import get_request_id

    assert get_request_id() == rid


def test_json_formatter_includes_request_id():
    set_request_id("abc123")
    get_logger("test.jsonfmt")
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", None, None)
    line = JsonFormatter().format(record)
    parsed = json.loads(line)
    assert parsed["msg"] == "hello"
    assert parsed["request_id"] == "abc123"
    assert parsed["level"] == "INFO"


def test_metrics_records_and_renders():
    m = Metrics()
    m.record_request("/v1/optimize-route", 200)
    m.record_query(latency_ms=12.0, rag_hit=True, degraded=False, carbon_saved_kg=5.0)
    m.record_query(latency_ms=40.0, rag_hit=False, degraded=True, carbon_saved_kg=2.0)

    text = m.render()
    assert "ecoroute_total_queries 2" in text
    assert "ecoroute_total_carbon_saved_kg 7.00" in text
    assert "ecoroute_degraded_queries 1" in text
    assert "ecoroute_rag_hits 1" in text
    assert "ecoroute_rag_misses 1" in text
    assert 'endpoint="/v1/optimize-route",status="200"' in text


def test_metrics_percentiles():
    m = Metrics()
    for v in [10, 20, 30, 40, 50]:
        m.record_query(latency_ms=float(v), rag_hit=True, degraded=False, carbon_saved_kg=0)
    text = m.render()
    assert "ecoroute_latency_p50_ms 30.00" in text
    assert "ecoroute_latency_p99_ms" in text


def test_heuristic_provider_deterministic():
    p = HeuristicProvider()
    a = p.synthesize("prompt", ["doc-a#0", "doc-b#1"])
    b = p.synthesize("prompt", ["doc-a#0", "doc-b#1"])
    assert a.text == b.text
    assert a.provider == "heuristic"
    assert a.degraded is False
    assert "doc-a#0" in a.text


def test_heuristic_provider_no_context():
    p = HeuristicProvider()
    r = p.synthesize("prompt", [])
    assert "No regulatory context" in r.text


def test_kompact_provider_is_degraded_stub():
    p = KompactProvider()
    r = p.synthesize("prompt", ["x"])
    assert r.provider == "kompact"
    assert r.degraded is True
    assert "kompact-stub" in r.text


def test_get_provider_factory():
    assert isinstance(get_provider("heuristic"), HeuristicProvider)
    assert isinstance(get_provider("kompact"), KompactProvider)
    # Unknown falls back to heuristic.
    assert isinstance(get_provider("anything"), HeuristicProvider)
