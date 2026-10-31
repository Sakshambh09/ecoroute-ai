# EcoRoute AI — production image
# Multi-stage, non-root, CPU-only. The FAISS index is built at image-build
# time so the container is fully functional on first boot (no model download
# at runtime). Rebuild the image after editing data/documents.json.

FROM python:3.12-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/hf-cache

COPY pyproject.toml README.md ./
COPY core ./core
COPY api ./api
COPY services ./services
COPY data ./data
COPY scripts ./scripts

RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir faiss-cpu sentence-transformers && \
    python scripts/build_index.py

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Non-root user for security
RUN groupadd -r ecoroute && useradd -r -g ecoroute ecoroute

COPY --from=builder /app /app
COPY --from=builder /hf-cache /home/ecoroute/.cache/huggingface

USER ecoroute
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
