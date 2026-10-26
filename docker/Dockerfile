FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/huggingface \
    MEMEX_QDRANT_PATH=/data/qdrant

WORKDIR /app

# Install the project and its runtime dependencies. Model weights are downloaded
# by sentence-transformers at runtime and cached in the mounted data directory.
COPY pyproject.toml README.md ./
COPY memex_backend ./memex_backend
RUN pip install --no-cache-dir .

RUN mkdir -p /data/qdrant /data/huggingface \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data

USER appuser
EXPOSE 8000

CMD ["uvicorn", "memex_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
