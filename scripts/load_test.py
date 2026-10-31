"""Concurrent load test for /v1/optimize-route (stdlib only, no locust).

Measures throughput and latency percentiles under a fixed concurrency, so the
README can quote real CPU numbers. Run the server first, then:

    python scripts/load_test.py --concurrency 8 --requests 200
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROUTES = [
    ("Delhi", "Jaipur", "heavy_truck", 28000),
    ("Mumbai", "Pune", "electric_van", 900),
    ("Chennai", "Bengaluru", "medium_truck", 12000),
    ("Kolkata", "Bhubaneswar", "cng_truck", 18000),
    ("Ahmedabad", "Surat", "light_truck", 2200),
]


def one_request(base_url: str, api_key: str, i: int) -> tuple[bool, float]:
    o, d, v, p = ROUTES[i % len(ROUTES)]
    body = json.dumps({"origin": o, "destination": d, "vehicle_type": v, "payload_kg": p}).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/optimize-route",
        data=body,
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
            return resp.status == 200, (time.perf_counter() - t0) * 1000
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False, (time.perf_counter() - t0) * 1000


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> int:
    ap = argparse.ArgumentParser(description="EcoRoute AI load test")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--api-key", default="dev-key-123")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--requests", type=int, default=200)
    args = ap.parse_args()

    print(f"Load test: {args.requests} requests @ concurrency {args.concurrency} -> {args.base_url}")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda i: one_request(args.base_url, args.api_key, i), range(args.requests)))
    wall = time.perf_counter() - t0

    ok = [r for r in results if r[0]]
    lat = [ms for _, ms in ok]
    errors = len(results) - len(ok)

    print("-" * 52)
    print(f"  Completed:        {len(ok)}/{args.requests}  ({errors} errors)")
    print(f"  Wall time:        {wall:.2f}s")
    print(f"  Throughput:       {len(ok) / wall:.1f} req/s")
    print(f"  Latency p50:      {percentile(lat, 0.50):.1f} ms")
    print(f"  Latency p95:      {percentile(lat, 0.95):.1f} ms")
    print(f"  Latency p99:      {percentile(lat, 0.99):.1f} ms")
    print(f"  Latency mean:     {statistics.mean(lat):.1f} ms" if lat else "  (no successes)")
    print(f"  Latency max:      {max(lat):.1f} ms" if lat else "")
    print("-" * 52)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
