"""Prometheus-format metrics + cumulative sustainability impact ledger.

Thread-safe (single lock). Exposes:
- Request counters by endpoint/status
- Latency histogram (p50/p95/p99) for /v1/optimize-route
- RAG hit rate and degraded-query count
- Cumulative CO2 saved (the live impact number for the demo)
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.requests_total: dict[tuple[str, str], int] = defaultdict(int)  # (endpoint, status)
        self.latencies: list[float] = []  # ms, optimize-route only
        self.rag_hits = 0
        self.rag_misses = 0
        self.degraded_queries = 0
        self.total_carbon_saved_kg = 0.0
        self.total_queries = 0

    def record_request(self, endpoint: str, status_code: int) -> None:
        with self._lock:
            self.requests_total[(endpoint, str(status_code))] += 1

    def record_query(self, latency_ms: float, rag_hit: bool, degraded: bool, carbon_saved_kg: float) -> None:
        with self._lock:
            self.total_queries += 1
            self.latencies.append(latency_ms)
            if len(self.latencies) > 5000:  # bounded ring
                self.latencies = self.latencies[-5000:]
            if rag_hit:
                self.rag_hits += 1
            else:
                self.rag_misses += 1
            if degraded:
                self.degraded_queries += 1
            self.total_carbon_saved_kg += carbon_saved_kg

    def _percentile(self, pct: float) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        k = (len(s) - 1) * pct
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    def render(self) -> str:
        with self._lock:
            lines = [
                "# EcoRoute AI metrics",
                f'ecoroute_uptime_seconds {time.time() - self.start_time:.1f}',
                f"ecoroute_total_queries {self.total_queries}",
                f"ecoroute_total_carbon_saved_kg {self.total_carbon_saved_kg:.2f}",
                f"ecoroute_degraded_queries {self.degraded_queries}",
                f"ecoroute_rag_hits {self.rag_hits}",
                f"ecoroute_rag_misses {self.rag_misses}",
                f"ecoroute_latency_p50_ms {self._percentile(0.50):.2f}",
                f"ecoroute_latency_p95_ms {self._percentile(0.95):.2f}",
                f"ecoroute_latency_p99_ms {self._percentile(0.99):.2f}",
            ]
            for (endpoint, status), count in sorted(self.requests_total.items()):
                lines.append(
                    f'ecoroute_requests_total{{endpoint="{endpoint}",status="{status}"}} {count}'
                )
            return "\n".join(lines) + "\n"
