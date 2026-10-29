"""The transcript the page shows (messages, product cards, option buttons), kept in Postgres so a refresh restores it.

This is separate from the graph's own state on purpose: that state is trimmed and summarised to keep prompts short,
while the page should always show the whole conversation.
"""
from psycopg.types.json import Jsonb

from app.db import pool

with pool.connection() as conn:
    conn.execute("""
        create table if not exists chat_log (
            id bigserial primary key,
            thread_id text not null,
            user_id text not null,
            role text not null,
            content text not null,
            payload jsonb not null default '{}',
            created_at timestamptz not null default now()
        )""")
    conn.execute("create index if not exists chat_log_thread_idx on chat_log (thread_id, id)")


def append(thread_id: str, user_id: str, entries: list[tuple[str, str, dict]]) -> None:
    """Save one turn: [(role, content, payload), ...] in order, in a single transaction."""
    with pool.connection() as conn, conn.transaction():
        for role, content, payload in entries:
            conn.execute(
                "insert into chat_log (thread_id, user_id, role, content, payload) values (%s, %s, %s, %s, %s)",
                (thread_id, user_id, role, content, Jsonb(payload)),
            )


def owned_by_someone_else(thread_id: str, user_id: str) -> bool:
    """True when this thread already has a transcript that belongs to another user (its state must not be shared)."""
    with pool.connection() as conn:
        row = conn.execute("select 1 from chat_log where thread_id = %s and user_id <> %s limit 1", (thread_id, user_id)).fetchone()
    return row is not None


def load(thread_id: str, user_id: str) -> list[dict]:
    """The conversation in order. Only the owner (same user_id) can read a thread."""
    with pool.connection() as conn:
        rows = conn.execute(
            "select role, content, payload from chat_log where thread_id = %s and user_id = %s order by id",
            (thread_id, user_id),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"], **r["payload"]} for r in rows]
