"""Agent orchestrator: the central decision-making hub.

Flow per query:
  1. Retrieve regulatory/emission context from the local RAG engine.
  2. Generate route candidates and compute carbon via the routing engine.
  3. Select the recommended route (lowest carbon) and the baseline (worst).
  4. Synthesize a citation-backed reasoning sequence via the inference
     provider (heuristic by default; Kompact AI in Phase 2).
  5. Attach a compute-cost breakdown (CPU seconds, energy, INR cost, and a
     cloud-LLM equivalent) to make the sustainability story measurable.
"""
from __future__ import annotations

import statistics
import time

import psutil

from api.schemas import (
    CostBreakdown,
    QueryRequest,
    QueryResponse,
    ReasoningStep,
    RouteOption,
    VehicleType,
)
from core.config import get_settings
from core.inference import InferenceProvider, InferenceResult, get_provider
from core.logger import get_logger
from services.ledger import CarbonLedger
from services.metrics import Metrics
from services.rag_service import RAGService
from services.routing_service import RouteCandidate, build_candidates, select_best

log = get_logger("services.agent")

# Assumed CPU power draw (W) for the host class used in energy estimates.
ASSUMED_CPU_WATTS = 65.0
# Tokens a comparable cloud LLM call would consume (prompt + completion).
CLOUD_EQUIV_TOKENS = 1200


class AgentService:
    def __init__(
        self,
        rag: RAGService,
        provider: InferenceProvider | None = None,
        metrics: Metrics | None = None,
        ledger: CarbonLedger | None = None,
    ) -> None:
        self.settings = get_settings()
        self.rag = rag
        self.provider = provider or get_provider(self.settings.inference_provider)
        self.metrics = metrics
        self.ledger = ledger
        self._proc = psutil.Process()

    def handle_query(self, payload: QueryRequest, request_id: str) -> QueryResponse:
        t0 = time.perf_counter()
        cpu_before = self._proc.cpu_times().user + self._proc.cpu_times().system

        # 1. RAG retrieval (regulatory + emission context for this vehicle class)
        query_text = (
            f"{payload.vehicle_type.value} emission factors carbon "
            f"{payload.origin} to {payload.destination} route optimization"
        )
        rag_outcome = self.rag.search(query_text, top_k=self.settings.rag_top_k)
        rag_context = [r.chunk.text for r in rag_outcome.results]
        citations = [r.chunk.chunk_id for r in rag_outcome.results]

        # 2. Route candidates + carbon math
        candidates = build_candidates(
            origin=payload.origin,
            destination=payload.destination,
            vehicle_type=payload.vehicle_type,
            payload_kg=payload.payload_kg,
            distance_km=payload.distance_km,
            constraints=payload.constraints,
        )
        recommended, baseline = select_best(candidates)
        carbon_saved = max(baseline.carbon_kg - recommended.carbon_kg, 0.0)

        # 3. Inference synthesis (decoupled provider)
        inference = self.provider.synthesize(
            prompt=f"Recommend a low-carbon route from {payload.origin} to {payload.destination}",
            context=citations,
        )

        # 4. Reasoning steps with citations
        steps = self._build_reasoning_steps(
            payload, rag_outcome.results, recommended, baseline, carbon_saved, inference
        )

        # 5. Compute cost breakdown
        cpu_after = self._proc.cpu_times().user + self._proc.cpu_times().system
        cpu_seconds = max(cpu_after - cpu_before, 0.0)
        cost = self._cost_breakdown(cpu_seconds)

        degraded = rag_outcome.degraded or inference.degraded
        response = QueryResponse(
            status="degraded" if degraded else "ok",
            request_id=request_id,
            recommended_route=self._to_route_option(recommended, is_recommended=True),
            alternatives=[
                self._to_route_option(c, is_recommended=False)
                for c in candidates
                if c.route_id != recommended.route_id
            ],
            estimated_carbon_saved_kg=round(carbon_saved, 2),
            baseline_carbon_kg=baseline.carbon_kg,
            reasoning_steps=steps,
            rag_context=rag_context,
            compute_cost=cost,
            degraded=degraded,
        )
        log.info(
            "query_processed",
            extra={
                "endpoint": "/v1/optimize-route",
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "carbon_saved_kg": response.estimated_carbon_saved_kg,
                "degraded": degraded,
            },
        )
        if self.metrics is not None:
            self.metrics.record_query(
                latency_ms=(time.perf_counter() - t0) * 1000,
                rag_hit=len(rag_outcome.results) > 0,
                degraded=degraded,
                carbon_saved_kg=response.estimated_carbon_saved_kg,
            )
        if self.ledger is not None:
            self.ledger.record(
                request_id=request_id,
                origin=payload.origin,
                destination=payload.destination,
                vehicle_type=payload.vehicle_type.value,
                carbon_saved_kg=response.estimated_carbon_saved_kg,
            )
        return response

    def _to_route_option(self, c: RouteCandidate, is_recommended: bool) -> RouteOption:
        return RouteOption(
            route_id=c.route_id,
            description=c.description,
            distance_km=c.distance_km,
            estimated_time_min=c.estimated_time_min,
            carbon_kg=c.carbon_kg,
            is_recommended=is_recommended,
        )

    def _build_reasoning_steps(
        self,
        payload: QueryRequest,
        rag_results: list,
        recommended: RouteCandidate,
        baseline: RouteCandidate,
        carbon_saved: float,
        inference: InferenceResult,
    ) -> list[ReasoningStep]:
        steps: list[ReasoningStep] = []

        steps.append(
            ReasoningStep(
                step=1,
                action="retrieve_context",
                detail=(
                    f"Retrieved {len(rag_results)} guideline chunks from the local "
                    f"knowledge base for '{payload.vehicle_type.value}' (no external calls)."
                ),
                sources=[r.chunk.chunk_id for r in rag_results],
            )
        )

        steps.append(
            ReasoningStep(
                step=2,
                action="generate_candidates",
                detail=(
                    f"Generated 3 candidate routes (direct, off-peak eco, consolidated) "
                    f"for {payload.origin} -> {payload.destination} with "
                    f"{payload.payload_kg:.0f} kg payload."
                ),
                sources=[],
            )
        )

        steps.append(
            ReasoningStep(
                step=3,
                action="compute_carbon",
                detail=(
                    f"Applied payload-adjusted emission factors plus idle-time burn. "
                    f"Recommended route emits {recommended.carbon_kg} kg CO2e vs "
                    f"{baseline.carbon_kg} kg for the highest-emission alternative."
                ),
                sources=[r.chunk.chunk_id for r in rag_results if "emission" in r.chunk.category],
            )
        )

        steps.append(
            ReasoningStep(
                step=4,
                action="select_route",
                detail=(
                    f"Selected {recommended.route_id} ({recommended.description}) — "
                    f"saves {carbon_saved:.2f} kg CO2e per trip."
                ),
                sources=[],
            )
        )

        steps.append(
            ReasoningStep(
                step=5,
                action="synthesize",
                detail=inference.text,
                sources=[],
            )
        )
        return steps

    def _cost_breakdown(self, cpu_seconds: float) -> CostBreakdown:
        energy_kwh = (cpu_seconds * ASSUMED_CPU_WATTS) / 3_600_000
        local_cost_inr = energy_kwh * self.settings.cpu_energy_cost_per_kwh_inr
        cloud_cost_usd = (
            CLOUD_EQUIV_TOKENS / 1_000_000 * self.settings.cloud_llm_cost_per_1m_tokens_usd
        )
        # Rough USD->INR for comparison display.
        cloud_cost_inr = cloud_cost_usd * 83.0
        return CostBreakdown(
            cpu_seconds=round(cpu_seconds, 4),
            energy_kwh=round(energy_kwh, 8),
            estimated_cost_inr=round(local_cost_inr, 6),
            cloud_llm_equivalent_cost_usd=round(cloud_cost_usd, 6),
            savings_vs_cloud_inr=round(cloud_cost_inr - local_cost_inr, 6),
        )

    def cost_comparison(self, queries: int = 1000) -> dict:
        """Dramatic CPU-vs-cloud cost analysis for the demo.

        Runs a representative query a few times to measure real CPU time
        (median, so a cold first query or a GC pause can't skew the number),
        then projects the cost of `queries` requests on the local CPU stack
        vs a cloud LLM API. Returns a plain dict (serialized by the route).
        """
        sample = QueryRequest(
            origin="Delhi",
            destination="Jaipur",
            vehicle_type=VehicleType.HEAVY_TRUCK,
            payload_kg=20000,
        )
        samples = [
            self.handle_query(sample, request_id="cost-comparison").compute_cost
            for _ in range(3)
        ]
        per_query_cpu_s = statistics.median(s.cpu_seconds for s in samples)
        per_query_local_inr = statistics.median(s.estimated_cost_inr for s in samples)
        per_query_cloud_usd = statistics.median(s.cloud_llm_equivalent_cost_usd for s in samples)

        local_total_inr = per_query_local_inr * queries
        cloud_total_usd = per_query_cloud_usd * queries
        cloud_total_inr = cloud_total_usd * 83.0
        savings_inr = cloud_total_inr - local_total_inr
        # Cap the ratio so it stays a finite, JSON-serializable number even when
        # the local cost rounds to ~0 (CPU is orders of magnitude cheaper).
        ratio = (cloud_total_inr / local_total_inr) if local_total_inr > 0 else 999_999.0
        ratio = min(ratio, 999_999.0)

        return {
            "queries": queries,
            "per_query": {
                "cpu_seconds": per_query_cpu_s,
                "local_cost_inr": per_query_local_inr,
                "cloud_llm_cost_usd": per_query_cloud_usd,
            },
            "total": {
                "local_cost_inr": round(local_total_inr, 4),
                "cloud_llm_cost_usd": round(cloud_total_usd, 4),
                "cloud_llm_cost_inr": round(cloud_total_inr, 4),
                "savings_inr": round(savings_inr, 4),
                "cloud_is_x_times_more_expensive": round(ratio, 1),
            },
            "assumptions": {
                "cpu_watts": ASSUMED_CPU_WATTS,
                "energy_cost_inr_per_kwh": self.settings.cpu_energy_cost_per_kwh_inr,
                "cloud_cost_usd_per_1m_tokens": self.settings.cloud_llm_cost_per_1m_tokens_usd,
                "cloud_equiv_tokens_per_query": CLOUD_EQUIV_TOKENS,
                "usd_to_inr": 83.0,
            },
        }
