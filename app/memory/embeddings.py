"""Local sentence embeddings for long-term memory search (no API calls, no tokens)."""
import os
import threading

MODEL = os.getenv("MEMORY_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DIMS = int(os.getenv("MEMORY_EMBED_DIMS", "384"))  # must match MODEL

_model = None
_lock = threading.Lock()


def _load():
    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            try:  # no network round trips once the model is cached
                _model = SentenceTransformer(MODEL, local_files_only=True)
            except Exception:
                _model = SentenceTransformer(MODEL)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Normalised vectors, so the store's score is cosine similarity."""
    return _load().encode(list(texts), normalize_embeddings=True).tolist()


def warm_up() -> None:
    """Load the model now (it takes ~15s the first time) instead of during someone's first message."""
    threading.Thread(target=embed, args=(["warm up"],), daemon=True).start()
