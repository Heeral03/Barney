# Barney

A multi-agent shopping assistant built on LangGraph. Barney asks a few targeted questions, searches several sources in parallel, and recommends one product with verified store prices, side-by-side comparisons and persistent personal context.

## Stack

- **Backend:** Python, LangGraph, FastAPI, Postgres with pgvector
- **Frontend:** Next.js (`web/`) with Google sign-in
- **LLM:** Groq (`openai/gpt-oss-120b` by default, with fallback models)
- **Sources:** SerpAPI Google Shopping, SerpKite, Tavily, DuckDuckGo

## Quick start

```bash
docker compose up -d postgres          # Postgres + pgvector on localhost:5433
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                   # then fill in the keys below
uvicorn app.api.main:app --reload      # API on http://localhost:8000

cd web && npm install && npm run dev   # frontend on http://localhost:3000
```

Tables are created on first start.

## Configuration

Set in `.env`:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | LLM access (required) |
| `SERPAPI_API_KEY` | Primary product search (required) |
| `SERPKITE_API_KEY` | Secondary shopping source |
| `TAVILY_API_KEY` | Web-search fallback |
| `DATABASE_URL` | Defaults to `postgresql://lily:lily@localhost:5433/lily` |
| `BACKEND_JWT_SECRET` | Shared with the frontend; 32+ characters (`openssl rand -base64 48`). The API returns 503 without it. |
| `GROQ_MODEL`, `GROQ_FALLBACK_MODELS`, `GROQ_CHAT_MODEL` | Optional model overrides |

### Google sign-in

The Next.js app holds the Google session and signs a short-lived token for each request it forwards to the API. The API (`app/auth.py`) trusts only that token. Guests get a random id in an httpOnly cookie, and their activity moves to their account on first sign-in (`POST /me/claim-guest`).

1. In Google Cloud Console, create a Web OAuth client. Set the origin to `http://localhost:3000` and the redirect URI to `http://localhost:3000/api/auth/callback/google`.
2. `cp web/.env.example web/.env.local` and set `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` and `AUTH_SECRET`.
3. Set the same `BACKEND_JWT_SECRET` in `web/.env.local` and `.env`.

## Architecture

```
START -> memory_in -> requirements -> memory_out -> supervisor -+-> (ask / chat) -> END
                                                                +-> compare -> END
                                                                +-> plan_research -> worker x N -> gather -> curator -> confirm_pick -> present -> END
                                                                +-> more -> END
```

| Node | File | Role |
|---|---|---|
| `memory_in` / `memory_out` | `app/agents/memory.py` | Load relevant long-term memories (pgvector) and save lasting preferences. Trims chat and keeps a rolling summary. |
| `requirements` | `app/agents/requirements.py` | LLM. Builds a per-product question plan, picks the next action, writes search queries. Small talk goes to `smalltalk.py`. |
| `supervisor` | `app/agents/supervisor.py` | Rule-based routing. Asks unanswered questions (at most 4 before results), then searches. |
| `plan_research`, `worker`, `gather` | `app/agents/researcher.py` | Parallel searches via LangGraph `Send`, with a fallback wave and a 15-minute cache. |
| `curator` | `app/agents/curator.py` | De-duplicates, filters by audience and budget, ranks, and keeps a reserve for "more". |
| `confirm_pick` | `app/agents/confirm.py` | Human-in-the-loop. Pauses the graph on a genuine close call (see below). No LLM. |
| `present` | `app/agents/presenter.py` | LLM. Recommends the best pick with reasons and a follow-up question. |
| `compare` | `app/agents/table.py` | LLM. Side-by-side specs, budget check and verdict. |
| `more` | `app/agents/presenter.py` | LLM. Next set of options with trade-offs against the pick. |

### Human in the loop

Two places keep a person in control.

**1. Close-call confirmation (runtime).** After ranking, `confirm_pick` checks whether the top three listings contain a real trade-off: one at least 25% cheaper and another rated at most 0.3 stars higher, both with 20 or more reviews. If so, it calls LangGraph `interrupt()` and the shopper chooses "Save money", "Higher rated" or "You decide". The paused run is held by the Postgres checkpointer, so it survives a refresh or restart. The question is returned as a normal reply with option buttons, so a tap resumes the run through `Command(resume=...)`; typing anything else starts a new turn. The presenter then honours the choice. It never pauses when one listing wins on both counts, when the shopper said "you decide", or when nothing fits the budget. Set `CONFIRM_CLOSE_CALLS=0` to switch it off.

**2. Feedback review (offline).** Thumbs-down and "wrong" feedback goes into a queue with the shopper's request attached. A reviewer labels each item `should_exclude` or `acceptable`, and the labels are exported as eval cases that the curator's filters are scored against. Confirmed failures become regression tests, and unfixed ones show up as a backlog.

```bash
python -m evals.review             # label the queue interactively
python -m evals.review --export    # append reviewed items to evals/datasets/reviewed.jsonl
python -m evals.run_reviewed       # score the filters against them
```

The same queue is available to admins (`ADMIN_USERS`) at `GET /admin/review` and `POST /admin/review/{id}`.

### Supporting modules

- **Pricing** (`app/pricing.py`, `app/sources/verify.py`): finds every store selling the pick, re-reads prices from store pages, and links to the cheapest reliable seller. Unverifiable prices are labelled "as listed".
- **Wishlist** (`app/wishlist.py`): saved items become taste memories.
- **LLM layer** (`app/llm.py`): ordered model fallback on quota errors, pydantic-validated JSON output with recovery.
- **Prompts:** `prompts/barney_*.txt`.

To add a source, write a function that returns offers and register a task type in `app/agents/researcher.py`.

## Testing

```bash
pytest                              # requires Postgres; no LLM or search keys needed
python -m evals.run_evals           # offline evals with pass/fail gates (no LLM, no network)
python -m evals.run_evals --agent   # also score the requirements agent (calls Groq)
python -m evals.run_evals --e2e     # also run the end-to-end task-completion eval
```

| Eval | Measures | Data |
|---|---|---|
| `run_filters` | Model-year extraction; curator filters catching stale, wrong-spec, wrong-audience and junk listings while keeping good ones | 30 titles, 8 scenarios |
| `run_requirements` | Budget parsing (offline); the requirements agent's decision, product, budget, skip, question-plan shape and query hygiene | 19 phrases, 20 cases |
| `run_reviewed` | Curator filters against listings that human reviewers flagged; regressions must stay fixed | `evals/datasets/reviewed.jsonl` |
| `run_task_completion` | End-to-end: does Barney pick a correct listing, avoid traps and finish within 3 turns (DeepEval) | 8 scenarios |

`run_evals` exits non-zero when a metric falls below its gate. Agent-level results vary between runs because they depend on the LLM, so use `python -m evals.run_requirements --repeat 3` for stable numbers. The `seed-*` rows in the reviewed dataset are hand-written starters; real cases arrive through the review tool.

## Repository layout

```
app/        LangGraph agents, API, memory, search sources
web/        Next.js frontend
prompts/    LLM prompts
evals/      Evaluation scripts, datasets and the reviewer tool
tests/      Unit and graph tests
```
