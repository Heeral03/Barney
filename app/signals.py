"""What the shopper does (opens a listing, hearts it, rates it) turned into things Barney may learn, only with their say-so.

Opens are recorded as events. Once several for the same kind of product pile up, one model call reads the titles and
proposes lasting tastes ("Likes over-ear headphones"). Those are only SUGGESTIONS until the shopper accepts them.
"""
import logging

from langchain_core.messages import HumanMessage
from psycopg.types.json import Jsonb

from app import settings
from app.db import pool
from app.llm import Structured, load_prompt
from app.memory import store as ltm
from app.wishlist import Taste

log = logging.getLogger(__name__)
PROMPT = load_prompt("barney_signals.txt")
extractor = Structured(Taste, '{"traits":[""]}')
NEEDED = 3  # opens of one kind of product before it is worth looking for a pattern
KINDS = ("open", "compare_store")

with pool.connection() as conn:
    conn.execute("""
        create table if not exists events (
            id bigserial primary key,
            user_id text not null,
            memory_id text not null,
            kind text not null,
            product text not null default '',
            title text not null,
            processed boolean not null default false,
            at timestamptz not null default now()
        )""")
    conn.execute("""
        create table if not exists suggestions (
            id bigserial primary key,
            memory_id text not null,
            text text not null,
            category text not null default 'general',
            status text not null default 'pending',
            created_at timestamptz not null default now(),
            unique (memory_id, text)
        )""")
    conn.execute("""
        create table if not exists feedback (
            id bigserial primary key,
            user_id text not null,
            thread_id text not null default '',
            product text not null default '',
            title text not null,
            verdict text not null,
            at timestamptz not null default now()
        )""")


def record_event(user_id: str, memory_id: str, kind: str, product: str, title: str) -> bool:
    if kind not in KINDS or not title.strip() or not settings.learning_on(user_id):
        return False
    with pool.connection() as conn:
        conn.execute("insert into events (user_id, memory_id, kind, product, title) values (%s, %s, %s, %s, %s)",
                     (user_id, memory_id, kind, product[:60], title[:200]))
    return True


def distil(memory_id: str, product: str) -> int:
    """Look at unprocessed opens for one product; propose tastes if there are enough. Returns suggestions added. Never raises."""
    try:
        with pool.connection() as conn:
            rows = conn.execute("select id, title from events where memory_id = %s and product = %s and not processed order by id desc limit 12",
                                (memory_id, product)).fetchall()
            if len(rows) < NEEDED:
                return 0
            conn.execute("update events set processed = true where id = any(%s)", ([r["id"] for r in rows],))
        listing = "\n".join(f"- {r['title']}" for r in rows)
        traits = extractor.invoke([PROMPT, HumanMessage(content=f"Product type: {product or 'unknown'}\nListings they opened:\n{listing}")]).traits
        category = (product or "general").replace("_", " ").split()[-1].lower()
        known = {m["text"].lower() for m in ltm.all_memories(ltm.ltm, memory_id)}
        added = 0
        with pool.connection() as conn:
            for t in traits[:3]:
                if t.strip() and t.strip().lower() not in known:
                    done = conn.execute("insert into suggestions (memory_id, text, category) values (%s, %s, %s) on conflict do nothing returning id",
                                        (memory_id, t.strip()[:140], category)).fetchone()
                    added += bool(done)
        return added
    except Exception as e:
        log.warning("could not look for a pattern in what they opened: %s", e)
        return 0


def pending(memory_id: str) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute("select id, text, category from suggestions where memory_id = %s and status = 'pending' order by id desc limit 20",
                            (memory_id,)).fetchall()


def decide(memory_id: str, suggestion_id: int, accept: bool) -> bool:
    with pool.connection() as conn:
        row = conn.execute("update suggestions set status = %s where id = %s and memory_id = %s and status = 'pending' returning text, category",
                           ("accepted" if accept else "dismissed", suggestion_id, memory_id)).fetchone()
    if row and accept:
        ltm.remember(ltm.ltm, memory_id, row["text"], row["category"], "preference", source="inferred")
    return bool(row)


def add_feedback(user_id: str, thread_id: str, product: str, title: str, verdict: str) -> None:
    if verdict in ("up", "down", "wrong"):
        with pool.connection() as conn:
            conn.execute("insert into feedback (user_id, thread_id, product, title, verdict) values (%s, %s, %s, %s, %s)",
                         (user_id, thread_id[:80], product[:60], title[:200], verdict))
