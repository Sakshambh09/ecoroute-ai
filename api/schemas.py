"""Pydantic models for strict request/response validation.

All field lengths are bounded to prevent oversized payloads from reaching
business logic. Enums constrain vehicle types so the routing math always
receives a known emission factor.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VehicleType(str, Enum):
    """Supported vehicle classes with defined emission factors."""

    LIGHT_TRUCK = "light_truck"
    MEDIUM_TRUCK = "medium_truck"
    HEAVY_TRUCK = "heavy_truck"
    ELECTRIC_VAN = "electric_van"
    CNG_TRUCK = "cng_truck"


class RouteOption(BaseModel):
    """A single candidate route returned to the client."""

    route_id: str = Field(..., description="Stable identifier for the route")
    description: str = Field(..., description="Human-readable route summary")
    distance_km: float = Field(..., ge=0, description="Total distance in km")
    estimated_time_min: float = Field(..., ge=0, description="Estimated travel time")
    carbon_kg: float = Field(..., ge=0, description="Estimated CO2e emitted (kg)")
    is_recommended: bool = Field(default=False)


class ReasoningStep(BaseModel):
    """One step in the agent's chain-of-reasoning, with source citations."""

    step: int
    action: str
    detail: str
    sources: list[str] = Field(default_factory=list, description="Cited chunk IDs")


class QueryRequest(BaseModel):
    """Incoming routing query."""

    origin: str = Field(..., min_length=1, max_length=120)
    destination: str = Field(..., min_length=1, max_length=120)
    vehicle_type: VehicleType = Field(default=VehicleType.LIGHT_TRUCK)
    payload_kg: float = Field(default=0.0, ge=0, le=50_000, description="Payload weight")
    distance_km: float | None = Field(
        default=None, ge=0, le=20_000, description="Optional known distance; else estimated"
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Local operational constraints (e.g. max_speed, avoid_highways)",
    )

    @field_validator("origin", "destination")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class CostBreakdown(BaseModel):
    """Sustainability/cost transparency for a single query."""

    cpu_seconds: float
    energy_kwh: float
    estimated_cost_inr: float
    cloud_llm_equivalent_cost_usd: float
    savings_vs_cloud_inr: float


class QueryResponse(BaseModel):
    """Final agent response."""

    status: str = Field(..., description="ok | degraded | error")
    request_id: str
    recommended_route: RouteOption
    alternatives: list[RouteOption] = Field(default_factory=list)
    estimated_carbon_saved_kg: float = Field(
        ..., ge=0, description="CO2e saved vs the highest-emission alternative"
    )
    baseline_carbon_kg: float = Field(..., ge=0, description="Carbon of the worst alternative")
    reasoning_steps: list[ReasoningStep]
    rag_context: list[str] = Field(
        default_factory=list, description="Retrieved guideline excerpts used"
    )
    compute_cost: CostBreakdown
    degraded: bool = Field(default=False, description="True if any subsystem fell back")


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str = "-"


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    version: str
    index_loaded: bool
    inference_provider: str
    auth_enabled: bool


class KnowledgeBaseInfo(BaseModel):
    document_count: int
    chunk_count: int
    categories: list[str]
    index_built_at: str | None
    embedding_model: str
