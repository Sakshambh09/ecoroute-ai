"""Inference provider abstraction — the Phase-2 Kompact AI swap point.

The agent never calls a concrete model directly; it depends on this
protocol. Swapping the generative backend is a single env var
(`INFERENCE_PROVIDER=heuristic|kompact`), which is exactly the decoupling
the architecture requires for the Kompact AI Runtime integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.logger import get_logger

log = get_logger("core.inference")


@dataclass(frozen=True)
class InferenceResult:
    text: str
    provider: str
    degraded: bool = False
    latency_ms: float = 0.0


@runtime_checkable
class InferenceProvider(Protocol):
    name: str

    def synthesize(self, prompt: str, context: list[str]) -> InferenceResult:
        """Produce the final reasoning synthesis for a routing decision."""
        ...


class HeuristicProvider:
    """Deterministic, zero-model reasoning synthesizer (default).

    Composes a concise, citation-backed rationale from the retrieved context
    and the computed carbon figures. No GPU, no network, fully reproducible.
    """

    name = "heuristic"

    def synthesize(self, prompt: str, context: list[str]) -> InferenceResult:
        import time

        t0 = time.perf_counter()
        lines = [
            "Selected the lowest-carbon candidate by combining distance, payload load factor, and idle time.",
        ]
        if context:
            lines.append(
                "Grounded in "
                + ", ".join(context[:3])
                + " (local knowledge base, no external calls)."
            )
        else:
            lines.append("No regulatory context retrieved; applied default emission factors.")
        lines.append("All computation executed on-CPU; no data left the host (privacy-first).")
        return InferenceResult(
            text=" ".join(lines),
            provider=self.name,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


class KompactProvider:
    """Phase-2 stub for the ZIROH Kompact AI Runtime.

    Mirrors the expected runtime interface (load model once, infer per call).
    When the finalist runtime is provisioned, implement `_infer` against the
    Kompact endpoint; everything upstream of this class is already decoupled.
    """

    name = "kompact"

    def __init__(self) -> None:
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            # TODO(phase-2): initialize the Kompact AI runtime client here.
            log.info("kompact_runtime_stub_init")
            self._loaded = True

    def synthesize(self, prompt: str, context: list[str]) -> InferenceResult:
        import time

        t0 = time.perf_counter()
        self._ensure_loaded()
        # Stub behavior: deterministic fallback so the system stays functional
        # until the real runtime is wired in.
        text = (
            "[kompact-stub] Reasoning synthesized via Kompact AI Runtime interface. "
            f"Context chunks: {len(context)}. "
            "Replace _infer() with the provisioned runtime call in Phase 2."
        )
        return InferenceResult(
            text=text,
            provider=self.name,
            degraded=True,  # stub is not the real model
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


def get_provider(name: str) -> InferenceProvider:
    if name == "kompact":
        return KompactProvider()
    return HeuristicProvider()
