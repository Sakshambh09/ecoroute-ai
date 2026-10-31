"""Retrieval quality eval: recall@k on golden queries.

Runs in BM25 mode (offline) so it always executes; when the dense index is
present it validates the hybrid path too. Each golden query lists the chunk
doc-ids that SHOULD appear in the top-k results.
"""
from __future__ import annotations

# (query, expected_doc_ids, k)
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


def test_recall_at_k(rag_service):
    failures = []
    for query, expected, k in GOLDEN:
        outcome = rag_service.search(query, top_k=k)
        retrieved = {r.chunk.doc_id for r in outcome.results}
        if not (retrieved & expected):
            failures.append(f"{query!r}: expected one of {expected}, got {retrieved}")
    assert not failures, "Retrieval recall failures:\n" + "\n".join(failures)


def test_top1_precision(rag_service):
    """For unambiguous queries, the best-matching doc should rank first."""
    strict = [
        ("electric van zero tailpipe emissions", "doc-electric-van-emission-factor"),
        ("Bharat Stage VI emission norms 2020", "doc-bs6-emission-norms"),
    ]
    for query, expected in strict:
        outcome = rag_service.search(query, top_k=3)
        assert outcome.results, f"no results for {query!r}"
        top_docs = {r.chunk.doc_id for r in outcome.results[:2]}
        assert expected in top_docs, f"{query!r}: top-2 = {top_docs}, expected {expected}"
