"""Sentence embeddings for long-term memory search.

Two ways to get them, chosen by environment:

  local (default)  fastembed (ONNX, no PyTorch). Runs inside this process, no API calls, but the model sits in RAM:
                   about 180 MB on top of the app's ~110 MB. Fine on a laptop or a 1-2 GB host.
  remote           any OpenAI-compatible /v1/embeddings endpoint. Nothing is loaded here, so the app stays near 110 MB:
                   the way to fit a 512 MB host. Set EMBED_API_URL (+ EMBED_API_KEY, EMBED_API_MODEL, and
                   EMBED_API_DIMENSIONS when the model can shorten its vectors). OpenAI, Jina, Voyage, Together and
                   Mistral all speak this shape.

MEMORY_EMBED_DIMS must equal the vectors' length (384 for the default local model). The store's table is created with
that size, so changing provider on a database that already holds memories means starting that table fresh.
"""
import logging
import math
import os
import threading
import time

log = logging.getLogger(__name__)

MODEL = os.getenv("MEMORY_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DIMS = int(os.getenv("MEMORY_EMBED_DIMS", "384"))  # must match the model's output
REMOTE_URL = os.getenv("EMBED_API_URL", "").strip()

_model = None
_lock = threading.Lock()


def _load():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding

            _model = TextEmbedding(model_name=MODEL, threads=1)
    return _model


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _remote(texts: list[str]) -> list[list[float]]:
    import httpx

    body: dict = {"model": os.environ.get("EMBED_API_MODEL", ""), "input": texts}
    if os.getenv("EMBED_API_DIMENSIONS"):
        body["dimensions"] = int(os.environ["EMBED_API_DIMENSIONS"])
    headers = {"Authorization": f"Bearer {os.environ.get('EMBED_API_KEY', '')}"}
    for attempt in (1, 2):  # one retry: a cold provider or a blip should not lose a memory
        try:
            r = httpx.post(REMOTE_URL, headers=headers, json=body, timeout=20)
            r.raise_for_status()
            rows = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
            vectors = [_unit(d["embedding"]) for d in rows]
            break
        except Exception as e:
            if attempt == 2:
                raise
            log.warning("embedding request failed, retrying: %s", e)
            time.sleep(1)
    if len(vectors) != len(texts) or any(len(v) != DIMS for v in vectors):
        raise ValueError(f"the embedding API returned vectors of length {len(vectors[0]) if vectors else 0}, "
                         f"but MEMORY_EMBED_DIMS is {DIMS}; set EMBED_API_DIMENSIONS or MEMORY_EMBED_DIMS to match")
    return vectors


def embed(texts: list[str]) -> list[list[float]]:
    """Normalised vectors, so the store's score is cosine similarity."""
    if REMOTE_URL:
        return _remote(list(texts))
    return [v.tolist() for v in _load().embed(list(texts))]


def warm_up() -> None:
    """Load the local model in the background instead of during someone's first message. Nothing to do for a remote API."""
    if not REMOTE_URL:
        threading.Thread(target=embed, args=(["warm up"],), daemon=True).start()
