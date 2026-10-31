"""Generate the EcoRoute AI pitch deck (PPTX) for ZIROH Build Next 2026.

Produces docs/EcoRoute_AI_Pitch_Deck.pptx — a 10-slide, 16:9 deck in the
product's dark design system, with real screenshots from the demo video.

Usage:
    python scripts/make_pitch_deck.py
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.presentation import Presentation as PresentationModel
from pptx.slide import Slide
from pptx.util import Inches, Length, Pt

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "deck_assets"
OUT = ROOT / "docs" / "EcoRoute_AI_Pitch_Deck.pptx"

# Design tokens (match static/index.html)
BG = RGBColor(0x07, 0x0B, 0x12)
PANEL = RGBColor(0x10, 0x18, 0x26)
PANEL_EDGE = RGBColor(0x1E, 0x2A, 0x3C)
TEXT = RGBColor(0xE9, 0xEE, 0xF6)
MUTED = RGBColor(0x8B, 0x96, 0xA8)
FAINT = RGBColor(0x5C, 0x67, 0x79)
ACCENT = RGBColor(0x2D, 0xD4, 0xA7)
BLUE = RGBColor(0x38, 0xBD, 0xF8)
AMBER = RGBColor(0xFB, 0xBF, 0x24)

FONT = "Inter"
SW, SH = Inches(13.333), Inches(7.5)


def _set_bg(slide: Slide) -> None:
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG


def _box(slide: Slide, x: int, y: int, w: int, h: int, fill: RGBColor, line: RGBColor | None = None) -> None:
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Length(x), Length(y), Length(w), Length(h))
    shp.adjustments[0] = 0.06
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False


def _text(slide: Slide, x: int, y: int, w: int, h: int, runs: list[tuple[str, float, RGBColor, bool]], align=PP_ALIGN.LEFT, line_spacing: float = 1.0) -> None:
    tb = slide.shapes.add_textbox(Length(x), Length(y), Length(w), Length(h))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for text, size, color, bold in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.bold = bold
        r.font.name = FONT
    tb.text_frame.auto_size = None


def _header(slide: Slide, kicker: str, title: str) -> None:
    _text(slide, Inches(0.6), Inches(0.42), Inches(10), Inches(0.3), [(kicker.upper(), 11, ACCENT, True)])
    _text(slide, Inches(0.6), Inches(0.68), Inches(12.1), Inches(0.8), [(title, 30, TEXT, True)])
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.62), Inches(1.42), Inches(0.55), Pt(3))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False


def _footer(slide: Slide, idx: int) -> None:
    _text(slide, Inches(0.6), Inches(7.08), Inches(8.0), Inches(0.3),
          [("EcoRoute AI  ·  ZIROH Build Next 2026", 9, FAINT, False)])
    _text(slide, Inches(12.3), Inches(7.08), Inches(0.5), Inches(0.3),
          [(str(idx), 9, FAINT, False)], align=PP_ALIGN.RIGHT)


def _kpi(slide: Slide, x: int, y: int, w: int, h: int, value: str, label: str, value_color: RGBColor = ACCENT) -> None:
    _box(slide, x, y, w, h, PANEL, PANEL_EDGE)
    _text(slide, x + Inches(0.22), y + Inches(0.16), w - Inches(0.44), Inches(0.55), [(value, 26, value_color, True)])
    _text(slide, x + Inches(0.22), y + h - Inches(0.52), w - Inches(0.44), Inches(0.4), [(label, 10.5, MUTED, False)])


def _bullets(slide: Slide, x: int, y: int, w: int, h: int, items: list[tuple[str, str]]) -> None:
    tb = slide.shapes.add_textbox(Length(x), Length(y), Length(w), Length(h))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for head, body in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(10)
        p.line_spacing = 1.05
        r1 = p.add_run()
        r1.text = "▸ " + head + "  "
        r1.font.size = Pt(13.5)
        r1.font.bold = True
        r1.font.color.rgb = ACCENT
        r1.font.name = FONT
        r2 = p.add_run()
        r2.text = body
        r2.font.size = Pt(13)
        r2.font.color.rgb = TEXT
        r2.font.name = FONT


def new_slide(prs: PresentationModel) -> Slide:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide)
    return slide


def main() -> None:
    prs = Presentation()
    prs.slide_width = SW
    prs.slide_height = SH

    # ---- 1. Title ----
    s = new_slide(prs)
    _box(s, Inches(0), Inches(0), SW, SH, BG)
    glow = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.2), Inches(-2.2), Inches(7.5), Inches(5.5))
    glow.fill.solid()
    glow.fill.fore_color.rgb = RGBColor(0x0E, 0x2A, 0x22)
    glow.line.fill.background()
    glow.shadow.inherit = False
    _box(s, Inches(0.9), Inches(1.5), Inches(0.72), Inches(0.72), ACCENT)
    _text(s, Inches(0.9), Inches(1.62), Inches(0.72), Inches(0.5), [("🌿", 24, BG, True)], align=PP_ALIGN.CENTER)
    _text(s, Inches(0.85), Inches(2.5), Inches(11.5), Inches(1.2), [("EcoRoute AI", 54, TEXT, True)])
    _text(s, Inches(0.9), Inches(3.55), Inches(11.5), Inches(0.6),
          [("Sustainable fleet routing that runs 100% on CPU", 22, ACCENT, False)])
    _text(s, Inches(0.9), Inches(4.35), Inches(11.0), Inches(1.2),
          [("Low-carbon route optimization grounded in a local RAG knowledge base. ", 14, MUTED, False),
           ("Every query runs on-device — no data leaves the host, no cloud bill.", 14, MUTED, False)], line_spacing=1.2)
    _box(s, Inches(0.9), Inches(5.9), Inches(4.6), Inches(0.52), PANEL, PANEL_EDGE)
    _text(s, Inches(1.1), Inches(5.99), Inches(4.3), Inches(0.35),
          [("ZIROH Build Next 2026  ·  Sustainable AI Challenge", 11.5, MUTED, True)])

    # ---- 2. Problem ----
    s = new_slide(prs)
    _header(s, "The problem", "Fleet routing is stuck between two bad options")
    _box(s, Inches(0.6), Inches(1.8), Inches(5.9), Inches(2.5), PANEL, PANEL_EDGE)
    _text(s, Inches(0.9), Inches(2.0), Inches(5.3), Inches(0.4), [("Cloud LLM routing", 16, AMBER, True)])
    _bullets(s, Inches(0.9), Inches(2.5), Inches(5.3), Inches(1.7), [
        ("Privacy", "route + cargo data shipped to third-party APIs"),
        ("Cost", "per-token billing at fleet scale is unsustainable"),
        ("Latency", "network round-trips on every decision"),
    ])
    _box(s, Inches(6.85), Inches(1.8), Inches(5.9), Inches(2.5), PANEL, PANEL_EDGE)
    _text(s, Inches(7.15), Inches(2.0), Inches(5.3), Inches(0.4), [("Classic heuristics", 16, AMBER, True)])
    _bullets(s, Inches(7.15), Inches(2.5), Inches(5.3), Inches(1.7), [
        ("Distance-only", "ignores payload, idle time, congestion"),
        ("No grounding", "no regulatory/emission context, no citations"),
        ("Opaque", "operators can't audit why a route was chosen"),
    ])
    _box(s, Inches(0.6), Inches(4.6), Inches(12.15), Inches(1.9), RGBColor(0x0E, 0x2A, 0x22), RGBColor(0x1D, 0x4A, 0x3C))
    _text(s, Inches(0.95), Inches(4.85), Inches(11.5), Inches(1.5), [
        ("Logistics drives ~10% of global CO₂ emissions. ", 17, TEXT, True),
        ("The industry needs routing that is low-carbon, auditable, private, and cheap enough to run on every trip — not just in the cloud.", 15, TEXT, False),
    ], line_spacing=1.25)
    _footer(s, 2)

    # ---- 3. Solution ----
    s = new_slide(prs)
    _header(s, "The solution", "One API call → the lowest-carbon route, with proof")
    _text(s, Inches(0.6), Inches(1.75), Inches(12.1), Inches(0.5),
          [("EcoRoute AI recommends the best route for any origin / destination / vehicle / payload — grounded in real emission & regulation documents, with a citation-backed reasoning trace.", 14.5, MUTED, False)], line_spacing=1.2)
    cards = [
        ("Local RAG grounding", "FAISS dense + BM25 sparse retrieval (RRF fusion) over 16 real emission & regulation documents — BS-VI, Euro VI."),
        ("Physical carbon model", "distance × payload-adjusted factor + idle-time burn, over real Haversine road distances for 29 Indian cities."),
        ("Citation-backed reasoning", "every recommendation ships with a 5-step trace and the exact documents it relied on. Auditable by design."),
        ("CPU-native & private", "all inference on-device. Zero external calls — data never leaves the host, and the compute bill is near zero."),
    ]
    pos = [(0.6, 2.55), (6.85, 2.55), (0.6, 4.75), (6.85, 4.75)]
    for (cx, cy), (head, body) in zip(pos, cards, strict=True):
        _box(s, Inches(cx), Inches(cy), Inches(5.9), Inches(2.0), PANEL, PANEL_EDGE)
        _text(s, Inches(cx + 0.3), Inches(cy + 0.2), Inches(5.3), Inches(0.4), [(head, 15, ACCENT, True)])
        _text(s, Inches(cx + 0.3), Inches(cy + 0.68), Inches(5.3), Inches(1.2), [(body, 12, TEXT, False)], line_spacing=1.15)
    _footer(s, 3)

    # ---- 4. How it works ----
    s = new_slide(prs)
    _header(s, "How it works", "A deterministic, explainable pipeline")
    steps = [
        ("1 · Retrieve", "Hybrid dense + sparse search over the local knowledge base for the vehicle class"),
        ("2 · Compute", "Resolve real road distance; generate 3 candidates (direct / off-peak eco / consolidated)"),
        ("3 · Select", "Pick the lowest-carbon route; baseline = worst alternative for the savings number"),
        ("4 · Synthesize", "Citation-backed reasoning via a pluggable inference provider"),
        ("5 · Report", "Route + carbon + reasoning + measured compute cost; update the impact ledger"),
    ]
    y = 1.85
    for head, body in steps:
        _box(s, Inches(0.6), Inches(y), Inches(12.15), Inches(0.86), PANEL, PANEL_EDGE)
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.85), Inches(y + 0.28), Inches(0.3), Inches(0.3))
        dot.fill.solid()
        dot.fill.fore_color.rgb = ACCENT
        dot.line.fill.background()
        dot.shadow.inherit = False
        _text(s, Inches(1.4), Inches(y + 0.1), Inches(3.0), Inches(0.6), [(head, 14, ACCENT, True)])
        _text(s, Inches(4.4), Inches(y + 0.1), Inches(8.2), Inches(0.66), [(body, 12.5, TEXT, False)], line_spacing=1.05)
        y += 1.0
    _footer(s, 4)

    # ---- 5. Product demo ----
    s = new_slide(prs)
    _header(s, "Product", "A production dashboard, not a notebook")
    img = ASSETS / "ui_result.png"
    if img.exists():
        s.shapes.add_picture(str(img), Inches(0.6), Inches(1.75), width=Inches(8.6))
    _box(s, Inches(9.5), Inches(1.85), Inches(3.25), Inches(4.6), PANEL, PANEL_EDGE)
    _bullets(s, Inches(9.75), Inches(2.1), Inches(2.8), Inches(4.2), [
        ("Live KPIs", "queries, cumulative CO₂e saved, latency, cost per query"),
        ("Route comparison", "carbon bars across all candidates"),
        ("Reasoning trace", "animated timeline with source citations"),
        ("Impact ledger", "persistent across restarts"),
    ])
    _footer(s, 5)

    # ---- 6. Cost at scale ----
    s = new_slide(prs)
    _header(s, "Cost-effectiveness", "The money shot: ₹0.01 vs ₹498 per 10,000 queries")
    img = ASSETS / "ui_cost.png"
    if img.exists():
        s.shapes.add_picture(str(img), Inches(0.6), Inches(1.8), width=Inches(7.6))
    _kpi(s, Inches(8.6), Inches(1.9), Inches(4.1), Inches(1.35), "₹0.01", "Local CPU stack · 10k queries (measured)")
    _kpi(s, Inches(8.6), Inches(3.45), Inches(4.1), Inches(1.35), "₹498", "Cloud LLM API · 10k queries", value_color=AMBER)
    _kpi(s, Inches(8.6), Inches(5.0), Inches(4.1), Inches(1.35), "₹497.99", "Saved per 10k queries — on a 65W CPU")
    _footer(s, 6)

    # ---- 7. Benchmarks ----
    s = new_slide(prs)
    _header(s, "Efficiency & accuracy", "Measured, reproducible, in CI")
    kpis = [
        ("~82 req/s", "single worker, concurrent load test"),
        ("p95 155 ms", "end-to-end query latency"),
        ("recall@3 = 1.00", "retrieval quality on golden set"),
        ("MRR = 1.00", "mean reciprocal rank, 8/8 perfect"),
        ("77 tests", "unit + integration + eval, all green"),
        ("0 CVEs", "pip-audit clean, scanned in CI"),
    ]
    for i, (value, label) in enumerate(kpis):
        cx = 0.6 + (i % 3) * 4.15
        cy = 1.9 + (i // 3) * 2.35
        _kpi(s, Inches(cx), Inches(cy), Inches(3.85), Inches(2.0), value, label, value_color=ACCENT if i % 2 == 0 else BLUE)
    _text(s, Inches(0.6), Inches(6.55), Inches(12), Inches(0.4),
          [("Every number above is reproducible: make loadtest · make retrieval-report · make test", 11.5, MUTED, False)])
    _footer(s, 7)

    # ---- 8. Security & privacy ----
    s = new_slide(prs)
    _header(s, "Security & privacy", "Privacy-first is an architecture decision, not a slogan")
    items = [
        ("Zero external calls", "RAG, routing, and inference all run on-device. Customer data never leaves the host — the core privacy guarantee."),
        ("API-key auth + rate limiting", "per-key sliding-window limits, bounded payloads, strict Pydantic validation on every field."),
        ("Production hardening", "non-root container, multi-stage Dockerfile, health checks, structured JSON logs with request-id correlation."),
        ("Supply-chain security", "pip-audit CVE scanning in CI; pinned dependencies; deterministic builds."),
    ]
    y = 1.85
    for head, body in items:
        _box(s, Inches(0.6), Inches(y), Inches(12.15), Inches(1.12), PANEL, PANEL_EDGE)
        _text(s, Inches(0.95), Inches(y + 0.14), Inches(3.6), Inches(0.8), [(head, 14.5, ACCENT, True)])
        _text(s, Inches(4.7), Inches(y + 0.14), Inches(7.8), Inches(0.85), [(body, 12.5, TEXT, False)], line_spacing=1.1)
        y += 1.26
    _footer(s, 8)

    # ---- 9. Architecture ----
    s = new_slide(prs)
    _header(s, "Architecture", "Modular by design — every layer is swappable")
    layers = [
        ("API layer", "FastAPI · Pydantic v2 · middleware (auth, rate-limit, request-id, error envelope)"),
        ("Agent orchestrator", "retrieve → compute → select → synthesize → report; per-query CPU/energy measurement"),
        ("Local RAG engine", "FAISS (all-MiniLM-L6-v2) + custom BM25 + Reciprocal Rank Fusion; graceful BM25-only degradation"),
        ("Domain engines", "deterministic carbon model · Haversine road distances (29 cities) · SQLite impact ledger"),
        ("Inference provider", "protocol-based: heuristic (default) ⇄ Kompact AI runtime — one env var, zero upstream changes"),
    ]
    y = 1.8
    for head, body in layers:
        _box(s, Inches(0.6), Inches(y), Inches(7.6), Inches(0.92), PANEL, PANEL_EDGE)
        _text(s, Inches(0.9), Inches(y + 0.1), Inches(2.9), Inches(0.7), [(head, 13.5, ACCENT, True)])
        _text(s, Inches(3.8), Inches(y + 0.1), Inches(4.3), Inches(0.75), [(body, 11, TEXT, False)], line_spacing=1.05)
        y += 1.04
    _box(s, Inches(8.5), Inches(1.8), Inches(4.25), Inches(5.1), PANEL, PANEL_EDGE)
    _text(s, Inches(8.8), Inches(2.0), Inches(3.7), Inches(0.4), [("Stack", 14, ACCENT, True)])
    _text(s, Inches(8.8), Inches(2.5), Inches(3.7), Inches(4.2), [
        ("Python 3.11 · FastAPI · Uvicorn", 12, TEXT, False),
        ("faiss-cpu · sentence-transformers", 12, TEXT, False),
        ("Pydantic v2 · pydantic-settings", 12, TEXT, False),
        ("SQLite · psutil · Prometheus metrics", 12, TEXT, False),
        ("Docker (multi-stage, non-root)", 12, TEXT, False),
        ("GitHub Actions: ruff → mypy → pytest → pip-audit → docker build", 12, TEXT, False),
    ], line_spacing=1.5)
    _footer(s, 9)

    # ---- 10. Phase 2 + close ----
    s = new_slide(prs)
    _header(s, "Phase 2 & why we win", "Built to grow into the Kompact AI runtime")
    _box(s, Inches(0.6), Inches(1.8), Inches(5.9), Inches(2.3), RGBColor(0x0E, 0x2A, 0x22), RGBColor(0x1D, 0x4A, 0x3C))
    _text(s, Inches(0.9), Inches(2.0), Inches(5.3), Inches(0.4), [("Kompact AI readiness", 16, ACCENT, True)])
    _text(s, Inches(0.9), Inches(2.5), Inches(5.3), Inches(1.5), [
        ("Inference sits behind an InferenceProvider protocol. ", 13, TEXT, False),
        ("INFERENCE_PROVIDER=kompact", 13, BLUE, True),
        (" swaps the heuristic synthesizer for the Kompact runtime with zero changes to the agent, API, or RAG layers.", 13, TEXT, False),
    ], line_spacing=1.2)
    _box(s, Inches(6.85), Inches(1.8), Inches(5.9), Inches(2.3), PANEL, PANEL_EDGE)
    _text(s, Inches(7.15), Inches(2.0), Inches(5.3), Inches(0.4), [("Why this wins", 16, ACCENT, True)])
    _bullets(s, Inches(7.15), Inches(2.5), Inches(5.3), Inches(1.5), [
        ("Sustainability", "per-query + cumulative CO₂e, grounded in real norms"),
        ("Cost", "₹0.01 vs ₹498 per 10k queries, measured"),
        ("Efficiency", "82 req/s, p95 155 ms, recall@3 1.00"),
    ])
    _box(s, Inches(0.6), Inches(4.4), Inches(12.15), Inches(2.1), PANEL, PANEL_EDGE)
    _text(s, Inches(0.95), Inches(4.65), Inches(11.5), Inches(1.7), [
        ("Try it in 30 seconds", 15, TEXT, True),
        ("make install && make index && make dev   →   http://localhost:8000", 14, BLUE, True),
        ("github.com/Sakshambh09/ecoroute-ai  ·  77 tests · green CI · Docker · one-command setup", 12.5, MUTED, False),
    ], line_spacing=1.4)
    _footer(s, 10)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"deck saved: {OUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
