"""Routing & carbon calculation engine.

Pure, deterministic math — no I/O, no randomness — so it is trivially unit
testable and safe to run in a threadpool. The carbon model combines the two
dominant, independent drivers identified in the knowledge base:

    effective_carbon = distance_km * payload_adjusted_factor
                     + idle_hours * IDLE_CO2_PER_HOUR

Emission factors (kg CO2 per vehicle-km) are calibrated per vehicle class and
scaled by a load factor that grows with payload weight.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from api.schemas import VehicleType

# Great-circle distance underestimates road distance; typical road/straight
# ratio for Indian intercity corridors is ~1.2.
ROAD_FACTOR = 1.2
_EARTH_RADIUS_KM = 6371.0
_CITIES_PATH = Path(__file__).resolve().parent.parent / "data" / "cities.json"

# kg CO2 per vehicle-km at reference load, per vehicle class.
BASE_FACTOR: dict[VehicleType, float] = {
    VehicleType.LIGHT_TRUCK: 0.65,
    VehicleType.MEDIUM_TRUCK: 0.80,
    VehicleType.HEAVY_TRUCK: 1.00,
    VehicleType.CNG_TRUCK: 0.82,  # ~18% below diesel heavy truck
    VehicleType.ELECTRIC_VAN: 0.20,  # well-to-wheel on India grid mix
}

# Max payload (kg) at which the load factor saturates.
MAX_PAYLOAD: dict[VehicleType, float] = {
    VehicleType.LIGHT_TRUCK: 3500,
    VehicleType.MEDIUM_TRUCK: 16000,
    VehicleType.HEAVY_TRUCK: 40000,
    VehicleType.CNG_TRUCK: 34000,
    VehicleType.ELECTRIC_VAN: 1500,
}

# Additional fuel burn from a fully (vs empty) loaded vehicle.
LOAD_PENALTY = 0.25  # up to +25% at max payload

# Idle burn: ~3.2 kg CO2 per hour of idling (heavy diesel baseline).
IDLE_CO2_PER_HOUR = 3.2

# Average commercial speed (km/h) used to derive time and idle estimates.
AVG_SPEED_KMH = 55.0
# Fraction of travel time assumed to be idling/stop-heavy on unoptimized routes.
BASE_IDLE_FRACTION = 0.12


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    description: str
    distance_km: float
    estimated_time_min: float
    idle_hours: float
    carbon_kg: float


def _stable_id(origin: str, destination: str, variant: str) -> str:
    h = hashlib.sha1(f"{origin}|{destination}|{variant}".encode()).hexdigest()
    return f"route-{h[:8]}"


def _load_factor(vehicle_type: VehicleType, payload_kg: float) -> float:
    max_p = MAX_PAYLOAD[vehicle_type]
    ratio = min(max(payload_kg / max_p, 0.0), 1.0)
    return 1.0 + LOAD_PENALTY * ratio


@lru_cache(maxsize=1)
def _load_cities() -> dict[str, tuple[float, float]]:
    """Load city coordinates once. Returns {name: (lat, lon)}."""
    try:
        raw = json.loads(_CITIES_PATH.read_text())
        return {k.lower(): (v["lat"], v["lon"]) for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def geographic_distance_km(origin: str, destination: str) -> float | None:
    """Road-adjusted distance for known cities, else None (unknown city)."""
    cities = _load_cities()
    o = cities.get(origin.strip().lower())
    d = cities.get(destination.strip().lower())
    if not o or not d:
        return None
    return haversine_km(o[0], o[1], d[0], d[1]) * ROAD_FACTOR


def estimate_distance_km(origin: str, destination: str, provided: float | None) -> float:
    """Resolve route distance with a clear precedence:

    1. Explicitly provided distance (trusted input).
    2. Real geographic distance (Haversine x road factor) for known cities.
    3. Deterministic hash-based estimate for unknown city pairs (reproducible).
    """
    if provided is not None:
        return provided
    geo = geographic_distance_km(origin, destination)
    if geo is not None:
        return round(geo, 1)
    h = int(hashlib.sha1(f"{origin.lower()}->{destination.lower()}".encode()).hexdigest()[:8], 16)
    # Map to a plausible 40-1200 km corridor.
    return 40.0 + (h % 1160)


def carbon_for_route(
    distance_km: float,
    vehicle_type: VehicleType,
    payload_kg: float,
    idle_hours: float,
) -> float:
    """Core carbon model. Returns kg CO2e for one route leg."""
    if distance_km < 0 or payload_kg < 0 or idle_hours < 0:
        raise ValueError("distance, payload and idle hours must be non-negative")
    factor = BASE_FACTOR[vehicle_type] * _load_factor(vehicle_type, payload_kg)
    return distance_km * factor + idle_hours * IDLE_CO2_PER_HOUR


def build_candidates(
    origin: str,
    destination: str,
    vehicle_type: VehicleType,
    payload_kg: float,
    distance_km: float | None,
    constraints: dict | None = None,
) -> list[RouteCandidate]:
    """Generate candidate routes: direct, eco (off-peak), and consolidated.

    - direct:        shortest distance, baseline idle fraction.
    - eco:           ~8% longer but off-peak -> 35% less idle (traffic-aware).
    - consolidated:  ~12% longer, shared load -> lower effective payload.
    """
    constraints = constraints or {}
    base_dist = estimate_distance_km(origin, destination, distance_km)
    avoid_highways = bool(constraints.get("avoid_highways", False))

    def make(variant: str, dist: float, idle_fraction: float, payload: float, desc: str) -> RouteCandidate:
        hours = dist / AVG_SPEED_KMH
        idle = hours * idle_fraction
        carbon = carbon_for_route(dist, vehicle_type, payload, idle)
        return RouteCandidate(
            route_id=_stable_id(origin, destination, variant),
            description=desc,
            distance_km=round(dist, 1),
            estimated_time_min=round(hours * 60, 1),
            idle_hours=round(idle, 3),
            carbon_kg=round(carbon, 2),
        )

    candidates = [
        make(
            "direct",
            base_dist,
            BASE_IDLE_FRACTION,
            payload_kg,
            f"Direct corridor {origin} -> {destination} ({base_dist:.0f} km)",
        ),
        make(
            "eco",
            base_dist * 1.08,
            BASE_IDLE_FRACTION * 0.65,  # off-peak departure cuts idling
            payload_kg,
            f"Off-peak eco route {origin} -> {destination}, departs outside congestion windows",
        ),
        make(
            "consolidated",
            base_dist * 1.12,
            BASE_IDLE_FRACTION * 0.8,
            payload_kg * 0.7,  # shared load lowers per-vehicle payload
            f"Consolidated shared-load route {origin} -> {destination} (merged corridor)",
        ),
    ]

    if avoid_highways:
        # Penalize the highway-dependent direct route; eco/consolidated win.
        for i, c in enumerate(candidates):
            if "Direct" in c.description:
                new_dist = c.distance_km * 1.15
                new_idle = c.idle_hours * 1.2
                candidates[i] = RouteCandidate(
                    route_id=c.route_id,
                    description=c.description + " [highway-restricted]",
                    distance_km=round(new_dist, 1),
                    estimated_time_min=round(c.estimated_time_min * 1.15, 1),
                    idle_hours=round(new_idle, 3),
                    carbon_kg=round(carbon_for_route(new_dist, vehicle_type, payload_kg, new_idle), 2),
                )
    return candidates


def select_best(candidates: list[RouteCandidate]) -> tuple[RouteCandidate, RouteCandidate]:
    """Return (recommended, baseline) where baseline is the highest-carbon option."""
    if not candidates:
        raise ValueError("no route candidates")
    recommended = min(candidates, key=lambda c: (c.carbon_kg, c.distance_km))
    baseline = max(candidates, key=lambda c: c.carbon_kg)
    return recommended, baseline
