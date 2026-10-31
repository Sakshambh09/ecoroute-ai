"""Unit tests for the routing & carbon math (the core IP)."""
from __future__ import annotations

import pytest

from api.schemas import VehicleType
from services.routing_service import (
    build_candidates,
    carbon_for_route,
    estimate_distance_km,
    geographic_distance_km,
    haversine_km,
    select_best,
)


def test_carbon_zero_distance_zero_idle():
    assert carbon_for_route(0, VehicleType.HEAVY_TRUCK, 0, 0) == 0.0


def test_carbon_scales_with_distance():
    a = carbon_for_route(100, VehicleType.HEAVY_TRUCK, 1000, 0)
    b = carbon_for_route(200, VehicleType.HEAVY_TRUCK, 1000, 0)
    assert b > a


def test_carbon_scales_with_payload():
    light = carbon_for_route(100, VehicleType.HEAVY_TRUCK, 0, 0)
    heavy = carbon_for_route(100, VehicleType.HEAVY_TRUCK, 40000, 0)
    assert heavy > light


def test_carbon_includes_idle():
    no_idle = carbon_for_route(100, VehicleType.HEAVY_TRUCK, 1000, 0)
    with_idle = carbon_for_route(100, VehicleType.HEAVY_TRUCK, 1000, 2.0)
    assert with_idle > no_idle


def test_electric_van_lower_carbon_than_diesel():
    diesel = carbon_for_route(100, VehicleType.LIGHT_TRUCK, 1000, 0)
    ev = carbon_for_route(100, VehicleType.ELECTRIC_VAN, 1000, 0)
    assert ev < diesel


def test_negative_inputs_raise():
    with pytest.raises(ValueError):
        carbon_for_route(-1, VehicleType.HEAVY_TRUCK, 0, 0)
    with pytest.raises(ValueError):
        carbon_for_route(100, VehicleType.HEAVY_TRUCK, -5, 0)


def test_estimate_distance_deterministic():
    d1 = estimate_distance_km("Delhi", "Jaipur", None)
    d2 = estimate_distance_km("Delhi", "Jaipur", None)
    assert d1 == d2
    assert 40 <= d1 <= 1200


def test_estimate_distance_uses_provided():
    assert estimate_distance_km("A", "B", 123.4) == 123.4


def test_haversine_known_pair():
    # Delhi -> Jaipur great-circle is ~235 km.
    d = haversine_km(28.6139, 77.2090, 26.9124, 75.7873)
    assert 220 < d < 250


def test_haversine_zero_for_same_point():
    assert haversine_km(20.0, 70.0, 20.0, 70.0) == 0.0


def test_geographic_distance_known_cities():
    d = geographic_distance_km("Delhi", "Jaipur")
    assert d is not None
    # Road-adjusted (~1.2x of ~235 km) should be ~280-290 km.
    assert 270 < d < 300


def test_geographic_distance_unknown_city_returns_none():
    assert geographic_distance_km("Delhi", "Atlantis") is None


def test_estimate_prefers_geographic_for_known_cities():
    d = estimate_distance_km("Mumbai", "Pune", None)
    # Mumbai->Pune is ~150 km road; must NOT be the hash estimate.
    assert 120 < d < 200


def test_estimate_falls_back_to_hash_for_unknown():
    d = estimate_distance_km("Nowhere", "Atlantis", None)
    assert 40 <= d <= 1200


def test_build_candidates_returns_three():
    cands = build_candidates("Delhi", "Jaipur", VehicleType.HEAVY_TRUCK, 20000, None)
    assert len(cands) == 3
    assert all(c.carbon_kg >= 0 for c in cands)


def test_select_best_recommends_lowest_carbon():
    cands = build_candidates("Delhi", "Jaipur", VehicleType.HEAVY_TRUCK, 20000, None)
    recommended, baseline = select_best(cands)
    assert recommended.carbon_kg <= baseline.carbon_kg
    assert recommended.carbon_kg == min(c.carbon_kg for c in cands)


def test_avoid_highways_penalizes_direct():
    normal = build_candidates("Delhi", "Jaipur", VehicleType.HEAVY_TRUCK, 20000, None)
    restricted = build_candidates(
        "Delhi", "Jaipur", VehicleType.HEAVY_TRUCK, 20000, None, {"avoid_highways": True}
    )
    direct_normal = next(c for c in normal if "Direct" in c.description)
    direct_restricted = next(c for c in restricted if "Direct" in c.description)
    assert direct_restricted.carbon_kg > direct_normal.carbon_kg


def test_empty_candidates_raise():
    with pytest.raises(ValueError):
        select_best([])
