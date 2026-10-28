"""
Web server for Barney: serves the chat page and a /chat endpoint.

Run:  uvicorn app.api.main:app --reload      then open http://localhost:8000
"""
import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage
from groq import RateLimitError
from pydantic import BaseModel

from app import history, overview, pricing, wishlist
from app.agents.common import as_memory
from app.graph import chatbot
from app.memory import store as ltm
from app.memory.embeddings import warm_up

log = logging.getLogger(__name__)
app = FastAPI()
warm_up()  # load the embedding model in the background so the first message isn't slow
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    user_id: str = "anonymous"  # stable per browser; long-term memory is keyed on it


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.post("/chat")
def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id, "user_id": req.user_id}, "recursion_limit": 25}
    try:
        result = chatbot.invoke({"messages": [HumanMessage(content=req.message)]}, config=config)
        answer = {
            "reply": result["messages"][-1].content,
            "options": result.get("options") or [],
            "products": [{**c, "product": (result.get("profile") or {}).get("product", "")} for c in result.get("cards") or []],
            "table": result.get("table"),
            "memory": {"recalled": [as_memory(m)["text"] for m in result.get("recalled") or []], "saved": result.get("saved") or []},
        }
    except RateLimitError:
        log.warning("Groq rate limit hit")
        answer = {"reply": "I've hit my AI usage limit for now 😅 Give me a few minutes and send that again.", "options": [], "products": []}
    except Exception as e:
        log.exception("chat turn failed")
        answer = {"reply": f"Sorry, something went wrong on my side ({type(e).__name__}). Please try again.", "options": [], "products": []}
    try:  # the transcript is for the page (errors included, so a refresh shows what you saw); it must not lose the answer
        history.append(req.thread_id, req.user_id, [
            ("user", req.message, {}),
            ("assistant", answer["reply"], {k: answer[k] for k in ("options", "products", "memory", "table") if k in answer}),
        ])
    except Exception as e:
        log.warning("could not save the transcript: %s", e)
    return answer


@app.get("/history")
def get_history(thread_id: str, user_id: str = "anonymous"):
    return history.load(thread_id, user_id)


@app.get("/memories")
def memories(user_id: str = "anonymous"):
    return [{"key": m["key"], "text": m["text"], "category": m.get("category", "general")}
            for m in ltm.all_memories(ltm.ltm, user_id)]


@app.delete("/memories/{key}")
def forget(key: str, user_id: str = "anonymous"):
    ltm.forget(ltm.ltm, user_id, key)
    return {"ok": True}


class WishlistRequest(BaseModel):
    user_id: str = "anonymous"
    product: str = ""
    offer: dict


@app.post("/wishlist")
def add_to_wishlist(req: WishlistRequest, background: BackgroundTasks):
    item_id = wishlist.add(req.user_id, req.offer, req.product)
    if item_id is not None:  # a new heart teaches Barney a taste; the model call runs after the response
        background.add_task(wishlist.learn_taste, ltm.ltm, req.user_id, req.offer, req.product)
    return {"id": item_id, "new": item_id is not None}


@app.get("/wishlist")
def get_wishlist(user_id: str = "anonymous"):
    return wishlist.items(user_id)


@app.delete("/wishlist/{item_id}")
def remove_from_wishlist(item_id: int, user_id: str = "anonymous"):
    wishlist.remove(user_id, item_id)
    return {"ok": True}


class CompareRequest(BaseModel):
    token: str


@app.post("/compare")
def compare_prices(req: CompareRequest):
    """Every store's price for one listing (the card's "Compare prices" button). Costs one SerpAPI search."""
    info = pricing.compare(req.token)
    slim = pricing.apply_to_offer({}, info)
    return {"stores": slim.get("stores", []), "cheapest": {k: slim.get(k) for k in ("price_display", "price_inr", "seller", "link", "link_domain", "price_verified")} if info.get("cheapest") else None,
            "text": pricing.comparison_text(slim.get("stores"))}


class TargetRequest(BaseModel):
    user_id: str = "anonymous"
    target_inr: float | None = None


@app.put("/wishlist/{item_id}/target")
def set_wishlist_target(item_id: int, req: TargetRequest):
    wishlist.set_target(req.user_id, item_id, req.target_inr)
    return {"ok": True}


class BudgetRequest(BaseModel):
    user_id: str = "anonymous"
    amount_inr: float | None = None


@app.get("/budget")
def get_budget(user_id: str = "anonymous"):
    return overview.overview(user_id)["budget"]


@app.put("/budget")
def put_budget(req: BudgetRequest):
    overview.set_budget(req.user_id, req.amount_inr)
    return overview.overview(req.user_id)["budget"]


@app.get("/overview")
def get_overview(user_id: str = "anonymous"):
    return overview.overview(user_id)


@app.get("/comparisons")
def get_comparisons(user_id: str = "anonymous", limit: int = 12):
    return overview.comparisons(user_id, min(max(limit, 1), 50))
