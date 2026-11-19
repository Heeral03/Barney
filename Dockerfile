# Barney API. Build:  docker build -t barney-api .   Run:  docker run -p 8000:8000 --env-file .env barney-api
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 FASTEMBED_CACHE_PATH=/app/.fastembed

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Only needed when the embeddings run inside the app (no EMBED_API_URL): fetch the model now, not on the first request.
# Build with --build-arg PRELOAD_EMBEDDINGS=0 to skip it when you use a remote embeddings API.
ARG PRELOAD_EMBEDDINGS=1
RUN if [ "$PRELOAD_EMBEDDINGS" = "1" ]; then python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"; fi

COPY app ./app
COPY prompts ./prompts
COPY frontend ./frontend

RUN useradd --create-home barney && chown -R barney /app
USER barney

# One worker on purpose: every extra worker is another copy of the app (and of the model, if it is local) in memory.
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
