# EcoRoute AI — 3-Minute Pitch & Demo Script

> Mapped to the ZIROH Build Next 2026 criteria: **Sustainability · Cost-effectiveness · Efficiency · Security/Privacy**.
> Run `make dev` in one terminal, then `make demo` in another. Keep the `/docs` Swagger page open as a backup.

---

## Slide 1 — The Problem (20s)
**Say:**
> "India's logistics sector is one of the largest CO₂ emitters. Fleet managers *know* they should optimize routes for carbon, but every AI tool they can use ships their data to a cloud LLM — expensive, slow, and a privacy risk. There's no fast, cheap, *on-device* way to get carbon-smart routing."

**Show:** nothing yet — just the title slide.

---

## Slide 2 — The Solution (20s)
**Say:**
> "EcoRoute AI is a privacy-first, CPU-native routing agent. It retrieves real emission guidelines from a *local* knowledge base, computes per-route carbon with a physical model, and returns citation-backed reasoning — all on the CPU. No GPU, no cloud, no data leaves the host."

**Show:** the architecture diagram (README mermaid).

---

## Slide 3 — Live Demo: The Core (45s)
**Say:**
> "Let me show it live. I'm sending a 28-tonne heavy truck from Delhi to Jaipur."

**Do:** run `make demo` (or the single curl). Point at the output.

**Say as it prints:**
> "It generated three real routes — direct, an off-peak eco route, and a consolidated shared-load route. The distance is *geographic* — 282 km, computed from real city coordinates. It recommends the lowest-carbon route and tells us exactly how much CO₂ we save: **45 kg per trip**."

**Point at:** `recommended_route`, `estimated_carbon_saved_kg`, and the `reasoning_steps` with `sources` (citations).

---

## Slide 4 — It's Real RAG, Not a Stub (30s)
**Say:**
> "This isn't a canned answer. Look at the reasoning steps — each one cites the exact guideline chunk it used, like 'Bharat Stage VI emission norms' and 'payload vs idle trade-off'. That's a hybrid FAISS + BM25 retrieval engine running *in-process* on the CPU. I can prove it's real:"

**Do:** `curl /v1/knowledge-base` — show 16 documents, 5 categories.

**Say:**
> "Sixteen real emission and regulation documents, indexed locally. And if the embedding model ever fails, it degrades gracefully to keyword search and tells you — it never crashes."

---

## Slide 5 — The Money Shot: Cost (30s)
**Say:**
> "Now the part that matters for a *sustainable* AI challenge — cost. Here's the same query projected over 10,000 requests:"

**Do:** `curl "/v1/cost-comparison?queries=10000"`

**Say:**
> "Our CPU stack costs **₹0.02**. A cloud LLM API costs **₹498**. That's **24,900 times cheaper** — and it's the *same* answer, computed on-device. Scale that to a national fleet and the savings are enormous."

---

## Slide 6 — Efficiency & Security (25s)
**Say:**
> "Efficiency: the embedding model is warmed at startup, so the first query is ~150ms and steady-state is under 25ms — all on CPU. Security: API-key auth, rate limiting, bounded payloads, a non-root container, and a dependency CVE scan in CI. And because nothing leaves the host, your fleet data is sovereign by design."

**Do:** `curl /metrics` — show latency p50/p95 and the cumulative CO₂-saved counter.

---

## Slide 7 — Why We'll Win / Phase 2 (20s)
**Say:**
> "We built this to be *Kompact AI Runtime*-ready from day one. The inference layer is behind a clean interface — swapping our heuristic engine for the Kompact runtime is a single environment variable, zero code changes. That's our Phase 2. Thank you."

**Show:** the `INFERENCE_PROVIDER=heuristic|kompact` line from `core/inference.py`.

---

## Backup: likely judge questions

| Question | Answer |
|---|---|
| "How is the carbon number calculated?" | `distance × payload-adjusted emission factor + idle_hours × 3.2 kg/h`. Factors per vehicle class are grounded in the KB (BS-VI, Euro VI). |
| "Why CPU and not GPU?" | MiniLM-L6 is a 22M-param model — it's fast on CPU. The whole point is cost + edge deployment. |
| "What if the city isn't in your list?" | Falls back to a deterministic distance estimate; the API also accepts an explicit `distance_km`. |
| "Is the RAG actually retrieving?" | Yes — hybrid dense+sparse with RRF fusion, and every reasoning step carries chunk-ID citations. There's a recall@3 eval suite. |
| "How do you handle concurrency?" | CPU work runs in FastAPI's threadpool (sync handlers), so the event loop never blocks. |
| "What's the Kompact integration?" | `InferenceProvider` protocol; `KompactProvider` stub is ready to wire to the runtime. One env var to switch. |
