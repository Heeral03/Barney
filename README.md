# Barney: multi-agent shopping buddy

## Run

```bash
docker compose up -d postgres          # Postgres + pgvector on localhost:5433
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload      # then open http://localhost:8000
pytest                                 # needs the Postgres above; no LLM or search keys needed
```

## Sign-in (Google)

The browser never says who it is. The Next.js app (`web/`) holds the Google sign-in session and signs a short-lived token for every
request it forwards to the API; the API (`app/auth.py`) only trusts that token. Visitors who have not signed in get a random
guest id in an httpOnly cookie, and everything they did is moved to their account the first time they sign in
(`POST /me/claim-guest`, `app/accounts.py`).

1. Google Cloud Console -> APIs & Services -> Credentials -> Create OAuth client ID (Web). Authorised JavaScript origin
   `http://localhost:3000`; redirect URI `http://localhost:3000/api/auth/callback/google`.
2. `cp web/.env.example web/.env.local` and fill in `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `AUTH_SECRET`.
3. Put the same `BACKEND_JWT_SECRET` (32+ characters, `openssl rand -base64 48`) in `web/.env.local` and in this folder's `.env`.
   The API answers 503 without it, on purpose.

`.env` needs `GROQ_API_KEY` and `SERPAPI_API_KEY` (`SERPKITE_API_KEY` is the second shopping source); `TAVILY_API_KEY` enables the web fallback. `DATABASE_URL` defaults to `postgresql://lily:lily@localhost:5433/lily`.
Tables are created on first start.

## Graph (`app/graph.py`)

```
START -> memory_in -> requirements -> memory_out -> supervisor -+-> (ask / chat) -> END
                                                                +-> compare -> END   (side by side)
                                                                +-> plan_research -> worker x N (parallel) -> gather -> curator -+-> present -> END
                                                                |        ^------ fallback sources, once -----|                  |
                                                                +-> more <-----------------------------------------------------+ (mode "more")
                                                                      |  ^ (nothing left: search again, appending)
                                                                      +--+-> END
```

| Node | File | Job |
|---|---|---|
| `memory_in` | `app/agents/memory.py` | LTM -> STM. Semantic search (pgvector) over this user's memories plus the facts about the person (name...). Product memories are only shown for that product. |
| `requirements` | `app/agents/requirements.py` | LLM, one call per turn (none for small talk: a greeting or thanks goes to one plain, fast chat call in `app/agents/smalltalk.py`, no JSON and a tiny prompt). The first time a product comes up it writes the **question plan**: the 3-5 attributes that decide which products are right for that kind of product (jeans: fit, rise, wash, occasion, budget; a desk: size, material, height adjustability...), each with tappable answers. A tapped answer is recorded with **no model call**. It also picks the action (`ask`, `search`, `alternatives`, `chat`), writes the search queries, and says what is worth remembering. A budget the model misses is parsed from the message. |
| `memory_out` | `app/agents/memory.py` | Saves what the requirements agent judged worth remembering (lasting facts and tastes: sizes, fit, colour, brand; no extra LLM call), the lasting answers to the question plan (one slot per question, so they never overwrite each other), and a pick the shopper accepts. Then trims the chat and folds old turns into a rolling summary. |
| `supervisor` | `app/agents/supervisor.py` | No LLM. Understand first: asks the next unanswered attribute of the question plan (at most 4 before results; "Just show me options" is always available from the second question). No repeated topics, no search without a product. Routes. |
| `plan_research`, `worker`, `gather` | `app/agents/researcher.py` | No LLM. One worker per query runs in parallel (LangGraph `Send`), each with a 12s limit. If the first wave finds too few priced listings, one fallback wave runs in parallel: a plain query, Tavily and DuckDuckGo. "More options" searches include the web sources from the start. Searches are cached for 15 minutes. |
| `curator` | `app/agents/curator.py` | No LLM. De-duplicates, drops listings for the wrong audience (Men's shoes in a women's search), applies the budget, ranks by rating, reviews and relevance, keeps the cheapest fit on the list, tags listings, and keeps a ranked `reserve` for more options. |
| `present` | `app/agents/presenter.py` | LLM. The single best pick with 2-3 reasons and one tailored follow-up question with tappable answers (a trade-off in the results, or a budget question built from the real price range). Pictures for the top candidates are fetched while the model thinks. |
| `compare` | `app/agents/table.py` | LLM. The side-by-side view: specifications read from the listing titles and normalised across options (never guessed: missing stays "not stated"), a check of each option against what the shopper said (the budget is computed from real prices), the verified price, the seller and a buy link per option, and a verdict that speaks to the shopper and the current pick. |
| `more` | `app/agents/presenter.py` | LLM. The next 4 listings the shopper has not seen with trade-offs against the pick: from what was found, then the reserve, then a new search that appends. |

**Wishlist** (`app/wishlist.py`): the heart on each card saves a listing. Each new heart is turned into taste memories ("Likes dark indigo jeans"), and the recent ones are shown to the requirements agent.

**Prices** (`app/pricing.py`): the same product is often listed at very different prices on different stores. For the pick, the app
asks SerpAPI for every store that sells it (price + direct link), marks which are reliable (big marketplaces and brand stores),
re-reads the price from the cheapest stores' own pages (`app/sources/verify.py`) and shows the cheapest RELIABLE store with its own
link. A price confirmed on the page gets a ✓; a page showing a different price replaces the listed one; a store that blocks
automated checks (AJIO, often Amazon) is shown as "as listed", never as confirmed. A cheaper store we cannot vouch for is mentioned,
not recommended. Every card shown is resolved this way, so the shopper never leaves Barney to compare: the buy link is always the seller's own
page (never Google). A card whose lookup failed offers a "Compare prices" button (`POST /compare`).

**What Barney is for.** Google finds products; Barney helps decide which one is worth buying *for you*: needs-based discovery (a question
plan per product), decision-ready comparisons (the `compare` view and the verified store prices), and persistent personal context made
explicit ("Matched on: Straight fit · High rise · under ₹1,500 · 🧠 ...", the wishlist, and saved preferences).

Sources: SerpAPI Google Shopping (primary: ~40 listings with pictures per call; free plan = 250 searches a month, so it takes the lead
query only and is skipped when nearly used up), then SerpKite for the other queries, then Tavily (restricted to Indian retailers) and DuckDuckGo as fallbacks; web results are
kept only if the URL is a single product page. SerpKite's free plan is 500 credits per day: when it runs out, the app notices and
uses the web sources until 00:00 UTC without waiting on it.

LLM calls per turn: `requirements` (1; none when a tapped answer leaves more questions), plus `present` or `more` (1) when listings are shown, and a summary call once the
chat passes 12 messages.

**Models** (`app/llm.py`): Groq limits tokens per model per day. The models are tried in order (`GROQ_MODEL`, then
`GROQ_FALLBACK_MODELS`); one that is out of quota fails instantly (the client's own sleep-and-retry is off, it used to hang a turn for
up to a minute) and is skipped until Groq says it has recovered. General conversation uses `GROQ_CHAT_MODEL` (default
`openai/gpt-oss-20b`) with the same fallbacks. If a model answers in prose instead of JSON, the reply is recovered from its text.

To add a source: write a function returning offers, add a task type in `app/agents/researcher.py` (`_run`, `gather`).

Prompts live in `prompts/barney_*.txt`. LLM output is JSON validated with pydantic (`Structured` in `app/llm.py`), with retries and recovery for gpt-oss quirks on Groq.
