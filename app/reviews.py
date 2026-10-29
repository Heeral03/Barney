"""What buyers say about one listing, in a few lines: the common praise and the common complaints.

The review texts come with the store lookup (same SerpAPI call), so this costs one model call and no extra search.
Summaries are remembered for a day. If there is no review text, only the star split is returned: nothing is invented.
"""
import time

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, field_validator

from app.llm import Structured, load_prompt
from app.sources import serpapi

PROMPT = load_prompt("barney_reviews.txt")
_TTL = 86400
_cache: dict[str, tuple[float, dict]] = {}


class Summary(BaseModel):
    praise: list[str] = Field(default_factory=list)
    complaints: list[str] = Field(default_factory=list)
    verdict: str = ""

    @field_validator("praise", "complaints", mode="before")
    @classmethod
    def _list(cls, v):
        return [str(x).strip() for x in (v or []) if str(x).strip()][:4]

    @field_validator("verdict", mode="before")
    @classmethod
    def _text(cls, v):
        return (v or "").strip()


summariser = Structured(Summary, '{"praise":[""],"complaints":[""],"verdict":""}')


def split(histogram: list[dict]) -> list[dict]:
    """The share of buyers at each star level, 5 down to 1, as whole percents."""
    total = sum(h.get("amount") or 0 for h in histogram)
    if not total:
        return []
    by = {h["stars"]: h.get("amount") or 0 for h in histogram}
    return [{"stars": s, "percent": round(100 * by.get(s, 0) / total)} for s in (5, 4, 3, 2, 1)]


def summarize(token: str) -> dict:
    hit = _cache.get(token)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    data = serpapi.reviews(token)
    out = {"rating": data["rating"], "count": data["count"], "split": split(data["histogram"]), "praise": [], "complaints": [], "verdict": ""}
    if data["snippets"]:
        texts = "\n\n".join(f"Review {i} ({s.get('rating') or '?'} stars): {s['text']}" for i, s in enumerate(data["snippets"], 1))
        s = summariser.invoke([PROMPT, HumanMessage(content=f"Overall: {data['rating']} stars from {data['count']} ratings.\n\n{texts}")])
        out.update(praise=s.praise, complaints=s.complaints, verdict=s.verdict)
    if out["split"] or out["praise"]:
        _cache[token] = (time.time(), out)
    return out
