"""Unit tests for Pydantic schemas: strict validation and bounds."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas import QueryRequest, VehicleType


def test_valid_request_minimal():
    q = QueryRequest(origin="Delhi", destination="Jaipur")
    assert q.vehicle_type == VehicleType.LIGHT_TRUCK
    assert q.payload_kg == 0.0
    assert q.distance_km is None
    assert q.constraints == {}


def test_origin_destination_stripped():
    q = QueryRequest(origin="  Delhi  ", destination=" Jaipur ")
    assert q.origin == "Delhi"
    assert q.destination == "Jaipur"


def test_blank_origin_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="   ", destination="Jaipur")


def test_blank_destination_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="Delhi", destination="")


def test_missing_fields_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="Delhi")  # type: ignore[call-arg]


def test_invalid_vehicle_type_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="A", destination="B", vehicle_type="spaceship")


def test_negative_payload_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="A", destination="B", payload_kg=-1)


def test_oversized_payload_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="A", destination="B", payload_kg=999_999)


def test_negative_distance_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="A", destination="B", distance_km=-5)


def test_oversized_origin_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(origin="x" * 121, destination="B")


def test_all_vehicle_types_accepted():
    for vt in VehicleType:
        q = QueryRequest(origin="A", destination="B", vehicle_type=vt)
        assert q.vehicle_type == vt


def test_constraints_passthrough():
    q = QueryRequest(
        origin="A",
        destination="B",
        constraints={"avoid_highways": True, "max_speed": 60},
    )
    assert q.constraints["avoid_highways"] is True
    assert q.constraints["max_speed"] == 60
