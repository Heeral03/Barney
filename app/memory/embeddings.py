"""Local sentence embeddings for long-term memory search (no API calls, no tokens).

Uses fastembed (ONNX runtime, no PyTorch) so the API fits in small hosts. The default model is the same
all-MiniLM-L6-v2 as before, so vectors already stored stay valid.
"""
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
            from fastembed import TextEmbedding

            _model = TextEmbedding(model_name=MODEL, threads=1)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Normalised vectors, so the store's score is cosine similarity."""
    return [v.tolist() for v in _load().embed(list(texts))]


def warm_up() -> None:
    """Load the model in the background instead of during someone's first message."""
    threading.Thread(target=embed, args=(["warm up"],), daemon=True).start()
