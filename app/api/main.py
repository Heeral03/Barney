"""
Web server for Barney: serves the chat page and a /chat endpoint.

Run:  uvicorn app.api.main:app --reload      then open http://localhost:8000
"""
import asyncio
import contextlib
import json
import logging
import os
import time
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from groq import RateLimitError
from pydantic import BaseModel

from app import accounts, alerts, analytics, auth, history, overview, pricing, reviews, settings, share, signals, timing, wishlist
from app.agents.common import as_memory
from app.graph import chatbot
from app.memory import store as ltm
from app.memory.embeddings import warm_up

log = logging.getLogger(__name__)
ALERT_EVERY_MINUTES = int(os.getenv("ALERT_INTERVAL_MINUTES", "360"))


async def _price_watch():
    """Every few hours: re-read the price of each wishlisted listing and raise alerts. Off when ALERTS=off."""
    while True:
        await asyncio.sleep(ALERT_EVERY_MINUTES * 60)
        try:
            log.info("price watch: %s", await asyncio.to_thread(alerts.check_all))
        except Exception:
            log.exception("price watch failed")


@contextlib.asynccontextmanager
async def lifespan(_app):
    task = asyncio.create_task(_price_watch()) if os.getenv("ALERTS", "on") != "off" else None
    yield
    if task:
        task.cancel()


app = FastAPI(lifespan=lifespan)
warm_up()  # load the embedding model in the background so the first message isn't slow
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    answers: dict[str, list[str]] | None = None  # a submitted questionnaire: {topic: [chosen values]}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.post("/chat")
def chat(req: ChatRequest, me: auth.Caller = Depends(auth.current_user)):
    if history.owned_by_someone_else(req.thread_id, me.id):
        raise HTTPException(403, "this conversation belongs to someone else")
    config = _config(req, me)
    started = time.monotonic()
    try:
        result = chatbot.invoke(_input(req), config=config)
        answer = _answer(result)
    except Exception as e:
        answer = _failure(e)
    _save_turn(req, me, answer, started)
    return answer


def _mem(me: auth.Caller) -> str:
    """Whose tastes this request reads and writes: the account's own, or the selected shopping profile's."""
    return settings.memory_id(me.id, me.profile)


def _config(req: ChatRequest, me: auth.Caller) -> dict:
    return {"configurable": {"thread_id": req.thread_id, "user_id": me.id, "memory_id": _mem(me)}, "recursion_limit": 25}


def _input(req: ChatRequest) -> dict:
    return {"messages": [HumanMessage(content=req.message)], "answers": req.answers or {}, "form": None}


def _answer(result: dict) -> dict:
    return {
        "reply": result["messages"][-1].content,
        "options": result.get("options") or [],
        "products": [{**c, "product": (result.get("profile") or {}).get("product", "")} for c in result.get("cards") or []],
        "table": result.get("table"),
        "form": result.get("form"),
        "memory": {"recalled": [as_memory(m)["text"] for m in result.get("recalled") or []], "saved": result.get("saved") or []},
    }


def _failure(e: Exception) -> dict:
    if isinstance(e, RateLimitError):
        log.warning("Groq rate limit hit")
        return {"reply": "I've hit my AI usage limit for now 😅 Give me a few minutes and send that again.", "options": [], "products": []}
    log.error("chat turn failed", exc_info=e)
    return {"reply": f"Sorry, something went wrong on my side ({type(e).__name__}). Please try again.", "options": [], "products": []}


def _kind(answer: dict) -> str:
    """What the turn amounted to, for the numbers: a questionnaire, results, nothing found, a comparison, or just talk."""
    if answer.get("form"):
        return "form"
    if answer.get("products"):
        return "results"
    if answer.get("table"):
        return "compare"
    return "empty" if str(answer.get("reply", "")).startswith("I couldn't find") else "chat"


def _save_turn(req: ChatRequest, me: auth.Caller, answer: dict, started: float | None = None, first: float | None = None) -> None:
    if started is not None:
        now = time.monotonic()
        analytics.track(me.id, "turn", kind=_kind(answer), total_ms=int((now - started) * 1000), first_ms=int(((first or now) - started) * 1000),
                        products=len(answer.get("products") or []))
    try:  # the transcript is for the page (errors included, so a refresh shows what you saw); it must not lose the answer
        history.append(req.thread_id, me.id, [
            ("user", req.message, {}),
            ("assistant", answer["reply"], {k: answer[k] for k in ("options", "products", "memory", "table", "form") if k in answer}),
        ])
    except Exception as e:
        log.warning("could not save the transcript: %s", e)


_PREVIEW_FIELDS = ("number", "title", "price_display", "seller", "image_url", "rating", "rating_count")


def _progress(node: str, update: dict) -> list[dict]:
    """What the page can show while the turn is still running: a short status, and the candidates as soon as they are ranked."""
    if node == "memory_in":
        return [{"type": "status", "text": "Understanding what you need…"}]
    if node == "supervisor":
        text = {"research": "Searching the stores…", "more": "Finding more options…", "compare": "Building the comparison…"}.get(update.get("route"))
        return [{"type": "status", "text": text}] if text else []
    if node == "curator":
        offers = [{k: o.get(k) for k in _PREVIEW_FIELDS} for o in (update.get("offers") or [])[:6]]
        return [{"type": "status", "text": "Picking the best one for you…"}, *([{"type": "preview", "products": offers}] if offers else [])]
    return []


def _turn_events(req: ChatRequest, me: auth.Caller):
    """The turn as newline-delimited JSON: status and preview events while it runs, then one `done` with the full answer."""
    config = _config(req, me)
    started, first, final = time.monotonic(), None, None
    try:
        for mode, chunk in chatbot.stream(_input(req), config=config, stream_mode=["updates", "values"]):
            if mode == "values":
                final = chunk
            else:
                for node, update in chunk.items():
                    if isinstance(update, dict):
                        for event in _progress(node, update):
                            first = first or time.monotonic()
                            yield json.dumps(event) + "\n"
        answer = _answer(final)
    except Exception as e:
        answer = _failure(e)
    _save_turn(req, me, answer, started, first)
    yield json.dumps({"type": "done", "answer": answer}) + "\n"


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, me: auth.Caller = Depends(auth.current_user)):
    if history.owned_by_someone_else(req.thread_id, me.id):
        raise HTTPException(403, "this conversation belongs to someone else")
    return StreamingResponse(_turn_events(req, me), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/history")
def get_history(thread_id: str, me: auth.Caller = Depends(auth.current_user)):
    return history.load(thread_id, me.id)


@app.get("/memories")
def memories(me: auth.Caller = Depends(auth.current_user)):
    return [{"key": m["key"], "text": m["text"], "category": m.get("category", "general"), "source": m.get("source", "said")}
            for m in ltm.all_memories(ltm.ltm, _mem(me))]


class MemoryEdit(BaseModel):
    text: str


@app.put("/memories/{key}")
def edit_memory(key: str, req: MemoryEdit, me: auth.Caller = Depends(auth.current_user)):
    if not ltm.edit(ltm.ltm, _mem(me), key, req.text):
        raise HTTPException(400, "could not change that memory")
    return {"ok": True}


@app.delete("/memories/{key}")
def forget(key: str, me: auth.Caller = Depends(auth.current_user)):
    ltm.forget(ltm.ltm, _mem(me), key)
    return {"ok": True}


class WishlistRequest(BaseModel):
    product: str = ""
    offer: dict


@app.post("/wishlist")
def add_to_wishlist(req: WishlistRequest, background: BackgroundTasks, me: auth.Caller = Depends(auth.current_user)):
    item_id = wishlist.add(me.id, req.offer, req.product)
    if item_id is not None:  # a new heart teaches Barney a taste; the model call runs after the response
        background.add_task(wishlist.learn_taste, ltm.ltm, me.id, req.offer, req.product, _mem(me))
    return {"id": item_id, "new": item_id is not None}


@app.get("/wishlist")
def get_wishlist(me: auth.Caller = Depends(auth.current_user)):
    return wishlist.items(me.id)


@app.delete("/wishlist/{item_id}")
def remove_from_wishlist(item_id: int, me: auth.Caller = Depends(auth.current_user)):
    wishlist.remove(me.id, item_id)
    return {"ok": True}


class CompareRequest(BaseModel):
    token: str


@app.post("/compare")
def compare_prices(req: CompareRequest, me: auth.Caller = Depends(auth.current_user)):
    """Every store's price for one listing (the card's "Compare prices" button). Costs one SerpAPI search."""
    info = pricing.compare(req.token)
    slim = pricing.apply_to_offer({}, info)
    return {"stores": slim.get("stores", []), "cheapest": {k: slim.get(k) for k in ("price_display", "price_inr", "seller", "link", "link_domain", "price_verified")} if info.get("cheapest") else None,
            "text": pricing.comparison_text(slim.get("stores"))}


class TargetRequest(BaseModel):
    target_inr: float | None = None


@app.put("/wishlist/{item_id}/target")
def set_wishlist_target(item_id: int, req: TargetRequest, me: auth.Caller = Depends(auth.current_user)):
    wishlist.set_target(me.id, item_id, req.target_inr)
    return {"ok": True}


class BudgetRequest(BaseModel):
    amount_inr: float | None = None


@app.get("/budget")
def get_budget(me: auth.Caller = Depends(auth.current_user)):
    return overview.overview(me.id)["budget"]


@app.put("/budget")
def put_budget(req: BudgetRequest, me: auth.Caller = Depends(auth.current_user)):
    overview.set_budget(me.id, req.amount_inr)
    return overview.overview(me.id)["budget"]


@app.get("/overview")
def get_overview(me: auth.Caller = Depends(auth.current_user)):
    alerts.remember_email(me.id, me.email)  # where a price-drop email goes
    return {**overview.overview(me.id), "alerts": len(alerts.unseen(me.id))}


@app.get("/alerts")
def get_alerts(me: auth.Caller = Depends(auth.current_user)):
    return alerts.unseen(me.id)


@app.post("/alerts/seen")
def alerts_seen(me: auth.Caller = Depends(auth.current_user)):
    alerts.mark_seen(me.id)
    return {"ok": True}


@app.post("/wishlist/{item_id}/check")
def check_price_now(item_id: int, me: auth.Caller = Depends(auth.current_user)):
    """Read the price on the store's own page right now."""
    found = alerts.check_one(me.id, item_id)
    if found is None:
        raise HTTPException(404, "not on your wishlist")
    return found


@app.get("/wishlist/{item_id}/history")
def price_history(item_id: int, me: auth.Caller = Depends(auth.current_user)):
    return alerts.history(me.id, item_id)


@app.get("/comparisons")
def get_comparisons(limit: int = 12, me: auth.Caller = Depends(auth.current_user)):
    return overview.comparisons(me.id, min(max(limit, 1), 50))


class ClaimRequest(BaseModel):
    guest_token: str


@app.post("/me/claim-guest")
def claim_guest(req: ClaimRequest, me: auth.Caller = Depends(auth.signed_in)):
    """After signing in: bring over what this browser did as a guest. Needs both proofs (the account and the guest)."""
    guest = auth.decode(req.guest_token)
    if not guest.guest:
        raise HTTPException(400, "not a guest token")
    return accounts.claim_guest(guest.id, me.id)


# ----------------------------------------------------------------------------- settings, profiles, onboarding
@app.get("/settings")
def get_settings(me: auth.Caller = Depends(auth.current_user)):
    return settings.get(me.id)


class SettingsRequest(BaseModel):
    learning: bool | None = None


@app.put("/settings")
def put_settings(req: SettingsRequest, me: auth.Caller = Depends(auth.current_user)):
    return settings.update(me.id, learning=req.learning)


class ProfileRequest(BaseModel):
    name: str


@app.post("/profiles")
def add_profile(req: ProfileRequest, me: auth.Caller = Depends(auth.current_user)):
    return settings.add_profile(me.id, req.name)


@app.delete("/profiles/{name}")
def delete_profile(name: str, me: auth.Caller = Depends(auth.current_user)):
    return settings.remove_profile(me.id, name)


class OnboardingRequest(BaseModel):
    categories: list[str] = []
    priority: str = ""
    spend: str = ""


_PRIORITIES = {
    "Best quality": "Prefers quality over the lowest price",
    "Best value": "Looks for the best value for money",
    "Lowest price": "Wants the lowest price that is still decent",
    "Latest models": "Always wants the newest model",
}


@app.post("/onboarding")
def onboarding(req: OnboardingRequest, me: auth.Caller = Depends(auth.current_user)):
    """Three taps on first sign-in. These are things the shopper said, so they are saved even if learning is paused."""
    from app.memory import writer

    cats = [c.strip()[:30] for c in req.categories if c.strip()][:6]
    items = [{"text": f"Usually shops for {', '.join(cats)}", "category": "person", "kind": "profile", "key": "onboarding:categories"}] if cats else []
    if req.priority in _PRIORITIES:
        items.append({"text": _PRIORITIES[req.priority], "category": "person", "kind": "preference", "key": "onboarding:priority"})
    if req.spend.strip():
        items.append({"text": f"Usually spends {req.spend.strip()[:30]} on a purchase", "category": "person", "kind": "profile", "key": "onboarding:spend"})
    for item in items:  # writer.save keeps two a turn, so save one at a time
        writer.save(ltm.ltm, _mem(me), [item], source="said")
    analytics.track(me.id, "onboarding_done", categories=len(cats))
    return settings.update(me.id, onboarded=True)


# ----------------------------------------------------------------------------- what they do: suggestions, feedback, numbers
class EventRequest(BaseModel):
    kind: str
    product: str = ""
    title: str


@app.post("/events")
def event(req: EventRequest, background: BackgroundTasks, me: auth.Caller = Depends(auth.current_user)):
    """The shopper opened a listing. Recorded only while learning is on; patterns become suggestions, never memories."""
    recorded = signals.record_event(me.id, _mem(me), req.kind, req.product, req.title)
    if recorded:
        background.add_task(signals.distil, _mem(me), req.product[:60])
    analytics.track(me.id, "card_open", kind=req.kind)
    return {"recorded": recorded}


@app.get("/suggestions")
def get_suggestions(me: auth.Caller = Depends(auth.current_user)):
    return signals.pending(_mem(me))


@app.post("/suggestions/{suggestion_id}/{decision}")
def decide_suggestion(suggestion_id: int, decision: str, me: auth.Caller = Depends(auth.current_user)):
    if decision not in ("accept", "dismiss") or not signals.decide(_mem(me), suggestion_id, decision == "accept"):
        raise HTTPException(404, "no such suggestion")
    return {"ok": True}


class FeedbackRequest(BaseModel):
    thread_id: str = ""
    product: str = ""
    title: str
    verdict: str


@app.post("/feedback")
def feedback(req: FeedbackRequest, me: auth.Caller = Depends(auth.current_user)):
    if req.verdict not in ("up", "down", "wrong"):
        raise HTTPException(400, "verdict must be up, down or wrong")
    signals.add_feedback(me.id, req.thread_id, req.product, req.title, req.verdict)
    return {"ok": True}


class TrackRequest(BaseModel):
    name: str


@app.post("/track")
def track(req: TrackRequest, me: auth.Caller = Depends(auth.current_user)):
    if req.name in analytics.CLIENT_EVENTS:
        analytics.track(me.id, req.name)
    return {"ok": True}


@app.get("/metrics")
def metrics(days: int = 30, me: auth.Caller = Depends(auth.current_user)):
    if me.id not in {a.strip() for a in os.getenv("ADMIN_USERS", "").split(",") if a.strip()}:
        raise HTTPException(403, "admins only")
    return analytics.summary(min(max(days, 1), 365))


# ----------------------------------------------------------------------------- reviews, sharing
@app.post("/reviews/summary")
def review_summary(req: CompareRequest, me: auth.Caller = Depends(auth.current_user)):
    """What buyers say about one listing. Uses the stored store lookup when there is one, so it rarely costs a search."""
    try:
        return reviews.summarize(req.token)
    except RateLimitError:
        raise HTTPException(429, "I\'ve hit my AI usage limit for now") from None
    except Exception as e:
        log.warning("review summary failed: %s", e)
        raise HTTPException(502, "could not read the reviews") from None


class ShareRequest(BaseModel):
    title: str = ""
    table: dict


@app.post("/share")
def create_share(req: ShareRequest, me: auth.Caller = Depends(auth.current_user)):
    analytics.track(me.id, "share_created")
    return {"id": share.create(req.title, req.table)}


@app.get("/share/{share_id}")
def get_share(share_id: str):
    """Public: anyone with the link sees the snapshot (no account, no search tokens)."""
    found = share.load(share_id)
    if not found:
        raise HTTPException(404, "this link does not exist")
    return found
