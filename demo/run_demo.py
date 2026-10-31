"""EcoRoute AI — one-command fleet demo.

Fires a realistic multi-vehicle fleet scenario at the running API and prints a
clean summary: recommended route, carbon saved per trip, and the CPU-vs-cloud
cost comparison. This is the "wow" moment for the demo.

Usage:
    make dev            # in one terminal
    make demo           # in another
    # or: python demo/run_demo.py --base-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# A realistic mixed fleet: long-haul diesel, urban EV, mid-range CNG.
SCENARIO = [
    {"origin": "Delhi", "destination": "Jaipur", "vehicle_type": "heavy_truck", "payload_kg": 28000},
    {"origin": "Mumbai", "destination": "Pune", "vehicle_type": "electric_van", "payload_kg": 900},
    {"origin": "Chennai", "destination": "Bengaluru", "vehicle_type": "medium_truck", "payload_kg": 12000},
    {"origin": "Kolkata", "destination": "Bhubaneswar", "vehicle_type": "cng_truck", "payload_kg": 18000},
    {"origin": "Ahmedabad", "destination": "Surat", "vehicle_type": "light_truck", "payload_kg": 2200},
    {"origin": "Hyderabad", "destination": "Vijayawada", "vehicle_type": "heavy_truck", "payload_kg": 32000},
]


def call(base_url: str, payload: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        f"{base_url}/v1/optimize-route",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_json(base_url: str, path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        f"{base_url}{path}",
        headers={"X-API-Key": api_key},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser(description="EcoRoute AI fleet demo")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="dev-key-123")
    args = parser.parse_args()

    print("=" * 78)
    print("  EcoRoute AI — Sustainable Fleet Routing Demo")
    print(f"  Target: {args.base_url}")
    print("=" * 78)

    try:
        health = get_json(args.base_url, "/health", args.api_key)
    except (urllib.error.URLError, ConnectionError) as exc:
        print(f"\n  [!] Could not reach the API at {args.base_url}: {exc}")
        print("  Start it first:  make dev   (or: uvicorn main:app --port 8000)")
        return 1

    print(f"  Service: {health['status']}  |  index_loaded: {health['index_loaded']}  |  "
          f"provider: {health['inference_provider']}\n")

    header = f"{'Route':<28} {'Vehicle':<14} {'Rec. km':>8} {'CO2e kg':>9} {'Saved kg':>9} {'CPU s':>8}"
    print(header)
    print("-" * len(header))

    total_saved = 0.0
    total_local_inr = 0.0
    total_cloud_usd = 0.0
    rows = 0

    for q in SCENARIO:
        try:
            r = call(args.base_url, q, args.api_key)
        except (urllib.error.URLError, ConnectionError) as exc:
            print(f"  [!] {q['origin']} -> {q['destination']}: {exc}")
            continue

        rec = r["recommended_route"]
        cost = r["compute_cost"]
        total_saved += r["estimated_carbon_saved_kg"]
        total_local_inr += cost["estimated_cost_inr"]
        total_cloud_usd += cost["cloud_llm_equivalent_cost_usd"]
        rows += 1

        route_label = f"{q['origin']} -> {q['destination']}"
        print(
            f"{route_label:<28} {q['vehicle_type']:<14} {rec['distance_km']:>8.1f} "
            f"{rec['carbon_kg']:>9.1f} {r['estimated_carbon_saved_kg']:>9.1f} {cost['cpu_seconds']:>8.4f}"
        )

    print("-" * len(header))
    print("\n  IMPACT SUMMARY")
    print(f"    Trips optimized:        {rows}")
    print(f"    Total CO2e saved:       {total_saved:.1f} kg")
    print(f"    CPU cost (local):       INR {total_local_inr:.6f}")
    print(f"    Cloud-LLM equivalent:   USD {total_cloud_usd:.6f}  (~INR {total_cloud_usd * 83:.4f})")
    savings = total_cloud_usd * 83 - total_local_inr
    print(f"    Cost saved vs cloud:    INR {savings:.4f}")

    # The money shot: project the cost gap at fleet scale.
    print("\n  COST COMPARISON @ 10,000 QUERIES  (GET /v1/cost-comparison)")
    try:
        cc = get_json(args.base_url, "/v1/cost-comparison?queries=10000", args.api_key)
        t = cc["total"]
        print(f"    Local CPU stack:        INR {t['local_cost_inr']:.2f}")
        print(f"    Cloud LLM API:          INR {t['cloud_llm_cost_inr']:.2f}  (USD {t['cloud_llm_cost_usd']:.2f})")
        print(f"    You save:               INR {t['savings_inr']:.2f}")
        print(f"    Cloud is {t['cloud_is_x_times_more_expensive']:,.0f}x more expensive")
    except (urllib.error.URLError, ConnectionError, KeyError) as exc:
        print(f"    [!] cost-comparison unavailable: {exc}")

    print("\n  All inference ran on-CPU. No data left the host. Privacy-first. \U0001F331")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
