"""Share a comparison: a snapshot saved under a random link anyone can open, to send to family before a big purchase."""
import secrets

from psycopg.types.json import Jsonb

from app.db import pool

with pool.connection() as conn:
    conn.execute("create table if not exists shares (id text primary key, payload jsonb not null, created_at timestamptz not null default now())")

_ROW_FIELDS = ("number", "title", "image_url", "best", "price_inr", "price_display", "price_verified", "seller", "seller_trusted",
               "link", "stores", "rating", "rating_count", "values", "matches", "year")


def create(title: str, table: dict) -> str:
    """Save a snapshot. Only the comparison itself is kept: no account, no thread, no search tokens."""
    rows = [{k: r.get(k) for k in _ROW_FIELDS} for r in (table.get("rows") or [])][:6]
    payload = {"title": (title or "Comparison")[:120], "table": {"specs": table.get("specs") or [], "requirements": table.get("requirements") or [], "rows": rows}}
    share_id = secrets.token_urlsafe(8)
    with pool.connection() as conn:
        conn.execute("insert into shares (id, payload) values (%s, %s)", (share_id, Jsonb(payload)))
    return share_id


def load(share_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute("select payload from shares where id = %s", (share_id,)).fetchone()
    return row["payload"] if row else None
