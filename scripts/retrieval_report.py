"""Retrieval quality report: recall@k, MRR, precision@k over the golden set.

Produces the quantitative RAG evidence for the demo — run after `make index`:

    python scripts/retrieval_report.py

Uses the same golden queries as tests/eval so the reported numbers match CI.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.rag_service import RAGService  # noqa: E402

# (query, expected doc-ids, k) — mirrors tests/eval/test_retrieval_quality.py
GOLDEN = [
    ("heavy truck idling fuel burn reduction", {"doc-idle-reduction-guideline", "doc-heavy-truck-emission-factor"}, 3),
    ("electric van urban delivery emissions", {"doc-electric-van-emission-factor"}, 3),
    ("Bharat Stage VI NOx limits commercial vehicles", {"doc-bs6-emission-norms"}, 3),
    ("load consolidation shared corridor carbon", {"doc-route-consolidation"}, 3),
    ("CNG truck CO2 reduction range", {"doc-cng-truck-emission-factor"}, 3),
    ("eco driving fuel consumption training", {"doc-eco-driving"}, 3),
    ("zero emission zone urban diesel restriction", {"doc-urban-zero-emission-zones"}, 3),
    ("payload weight idle trade off optimization", {"doc-payload-idle-interaction"}, 3),
]


def main() -> int:
    rag = RAGService()
    rag.load()
    mode = "hybrid (dense+sparse)" if not rag.degraded else "BM25-only (degraded)"
    print(f"Retrieval quality report — {rag.chunk_count} chunks, mode: {mode}\n")

    header = f"{'Query':<48} {'Recall@3':>9} {'P@3':>6} {'MRR':>6}  Top-1 doc"
    print(header)
    print("-" * len(header))

    recalls, precisions, rrs = [], [], []
    for query, expected, k in GOLDEN:
        out = rag.search(query, top_k=k)
        retrieved = [r.chunk.doc_id for r in out.results]
        hits = [d for d in retrieved if d in expected]
        recall = len(set(hits)) / len(expected)
        precision = len(hits) / k
        # Reciprocal rank of the first relevant doc.
        rr = 0.0
        for i, d in enumerate(retrieved):
            if d in expected:
                rr = 1.0 / (i + 1)
                break
        recalls.append(recall)
        precisions.append(precision)
        rrs.append(rr)
        top1 = retrieved[0] if retrieved else "-"
        print(f"{query[:47]:<48} {recall:>9.2f} {precision:>6.2f} {rr:>6.2f}  {top1}")

    print("-" * len(header))
    n = len(GOLDEN)
    print(f"{'AVERAGE':<48} {sum(recalls) / n:>9.2f} {sum(precisions) / n:>6.2f} {sum(rrs) / n:>6.2f}")
    print(f"\nQueries: {n} | Perfect recall: {sum(1 for r in recalls if r == 1.0)}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
