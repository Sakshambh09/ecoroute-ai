"""Build the persisted FAISS index + chunk metadata from data/documents.json.

Run once (and whenever documents change):
    python scripts/build_index.py

Outputs (in data/):
    index.faiss      - FAISS inner-product index over L2-normalized embeddings
    index.vectors.npy- raw embedding matrix (for fast boot load)
    chunks.json      - chunk metadata (id, doc, category, region, text)
    index.meta.json  - build timestamp + model name
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from core.config import get_settings
from core.logger import get_logger
from services.rag_service import chunk_documents

log = get_logger("scripts.build_index")


def main() -> int:
    settings = get_settings()
    t0 = time.perf_counter()

    if not settings.documents_path.exists():
        log.error("documents_missing", extra={"path": str(settings.documents_path)})
        return 1

    documents = json.loads(settings.documents_path.read_text())
    chunks = chunk_documents(documents)
    texts = [c.text for c in chunks]
    log.info("chunked", extra={"documents": len(documents), "chunks": len(chunks)})

    try:
        import faiss
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        log.error("dependency_missing", extra={"error": str(exc)})
        print(f"Missing dependency: {exc}. Install with: pip install faiss-cpu sentence-transformers")
        return 1

    model = SentenceTransformer(settings.embedding_model)
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True).astype("float32")
    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)  # inner product == cosine on normalized vectors
    index.add(embeddings)

    settings.index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(settings.index_path))
    np.save(settings.index_path.with_suffix(".vectors.npy"), embeddings)
    settings.chunks_path.write_text(json.dumps([c.__dict__ for c in chunks], indent=2))
    settings.index_path.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "built_at": datetime.now(timezone.utc).isoformat(),
                "model": settings.embedding_model,
                "dim": dim,
                "chunks": len(chunks),
            },
            indent=2,
        )
    )

    log.info(
        "index_built",
        extra={
            "chunks": len(chunks),
            "dim": dim,
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    )
    print(f"Index built: {len(chunks)} chunks, dim={dim}, in {(time.perf_counter() - t0):.1f}s")
    print(f"  {settings.index_path}")
    print(f"  {settings.chunks_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
