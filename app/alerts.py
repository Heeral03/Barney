"""Price history and price alerts for the wishlist.

A background job re-reads the price on each wishlisted listing's own store page (free: no search credits), records it, and
raises an alert when it reaches the shopper's target price. Alerts show in the app; an email goes out too when SMTP is set up.
Stores that block automated reads are simply skipped: nothing is claimed about a price we could not see.
"""
import logging
import os
import smtplib
import time
from email.message import EmailMessage

from psycopg.types.json import Jsonb

from app.db import pool
from app.sources.verify import page_price
from app.tools.products import inr

log = logging.getLogger(__name__)
PAGE_TIMEOUT = 8

with pool.connection() as conn:
    conn.execute("""
        create table if not exists price_checks (
            id bigserial primary key,
            wishlist_id bigint not null,
            price_inr numeric not null,
            checked_at timestamptz not null default now()
        )""")
    conn.execute("create index if not exists price_checks_item_idx on price_checks (wishlist_id, checked_at)")
    conn.execute("""
        create table if not exists alerts (
            id bigserial primary key,
            user_id text not null,
            wishlist_id bigint not null,
            title text not null,
            price_inr numeric not null,
            target_inr numeric not null,
            link text,
            seen boolean not null default false,
            created_at timestamptz not null default now(),
            unique (wishlist_id, price_inr)
        )""")
    conn.execute("create table if not exists user_emails (user_id text primary key, email text not null)")


def remember_email(user_id: str, email: str) -> None:
    if not email or user_id.startswith("guest:"):
        return
    with pool.connection() as conn:
        conn.execute("insert into user_emails (user_id, email) values (%s, %s) "
                     "on conflict (user_id) do update set email = excluded.email", (user_id, email))


def send_email(to: str, subject: str, body: str) -> bool:
    """Plain SMTP, configured with SMTP_HOST (+ SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM). False when not set up or failed."""
    host = os.getenv("SMTP_HOST")
    if not host:
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "barney@localhost", to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
            smtp.starttls()
            if os.getenv("SMTP_USER"):
                smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except Exception as e:
        log.warning("could not send the alert email: %s", e)
        return False


def _email_for(user_id: str) -> str | None:
    with pool.connection() as conn:
        row = conn.execute("select email from user_emails where user_id = %s", (user_id,)).fetchone()
    return row["email"] if row else None


def record(item_id: int, price: float) -> None:
    """Remember this price for the item and show it on the wishlist."""
    with pool.connection() as conn, conn.transaction():
        conn.execute("insert into price_checks (wishlist_id, price_inr) values (%s, %s)", (item_id, price))
        conn.execute("update wishlist set offer = offer || %s where id = %s",
                     (Jsonb({"price_inr": price, "price_display": inr(price)}), item_id))


def check_item(row: dict) -> dict:
    """Read one wishlisted listing's page. Returns {"price": float | None, "alert": bool}. Never raises."""
    offer = row["offer"] or {}
    try:
        price = page_price(offer.get("link"), PAGE_TIMEOUT) if offer.get("link") else None
    except Exception as e:
        log.warning("price check failed for item %s: %s", row["id"], e)
        price = None
    if price is None:
        return {"price": None, "alert": False}
    record(row["id"], price)
    target = float(row["target_inr"]) if row.get("target_inr") is not None else None
    if target is None or price > target:
        return {"price": price, "alert": False}
    with pool.connection() as conn:
        made = conn.execute(
            "insert into alerts (user_id, wishlist_id, title, price_inr, target_inr, link) values (%s, %s, %s, %s, %s, %s) "
            "on conflict (wishlist_id, price_inr) do nothing returning id",
            (row["user_id"], row["id"], row["title"], price, target, offer.get("link"))).fetchone()
    if made:  # a new low that reached the target: tell them once
        email = _email_for(row["user_id"])
        if email:
            send_email(email, f"Price drop: {row['title'][:60]} is now {inr(price)}",
                       f"{row['title']}\n\nIt is now {inr(price)}, at or below your target of {inr(target)}.\n{offer.get('link') or ''}\n\n- Barney")
    return {"price": price, "alert": bool(made)}


def _rows(where: str = "", params: tuple = (), limit: int = 200) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            f"select id, user_id, title, offer, target_inr from wishlist where offer->>'link' is not null {where} "
            f"order by id desc limit %s", (*params, limit)).fetchall()


def check_all(limit: int = 200) -> dict:
    """The scheduled job: every wishlisted listing that has a link."""
    rows = _rows(limit=limit)
    results = [check_item(r) for r in rows]
    return {"checked": sum(r["price"] is not None for r in results), "alerts": sum(r["alert"] for r in results), "items": len(rows)}


def check_one(user_id: str, item_id: int) -> dict | None:
    """"Check now" for one of the shopper's own items. None when it is not theirs."""
    rows = _rows("and user_id = %s and id = %s", (user_id, item_id), 1)
    return {**check_item(rows[0]), "checked_at": time.time()} if rows else None


def unseen(user_id: str) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute("select id, wishlist_id, title, price_inr, target_inr, link, extract(epoch from created_at) as at "
                            "from alerts where user_id = %s and not seen order by id desc limit 50", (user_id,)).fetchall()
    return [{**r, "price_inr": float(r["price_inr"]), "target_inr": float(r["target_inr"]), "at": float(r["at"])} for r in rows]


def mark_seen(user_id: str) -> None:
    with pool.connection() as conn:
        conn.execute("update alerts set seen = true where user_id = %s and not seen", (user_id,))


def history(user_id: str, item_id: int, limit: int = 60) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            "select p.price_inr, extract(epoch from p.checked_at) as at from price_checks p join wishlist w on w.id = p.wishlist_id "
            "where w.user_id = %s and w.id = %s order by p.checked_at desc limit %s", (user_id, item_id, limit)).fetchall()
    return [{"price_inr": float(r["price_inr"]), "at": float(r["at"])} for r in reversed(rows)]


def stats(item_ids: list[int]) -> dict[int, dict]:
    """Lowest, highest and last-checked price seen for each item."""
    if not item_ids:
        return {}
    with pool.connection() as conn:
        rows = conn.execute("select wishlist_id, min(price_inr) as lo, max(price_inr) as hi, count(*) as n, "
                            "extract(epoch from max(checked_at)) as at from price_checks where wishlist_id = any(%s) group by wishlist_id",
                            (item_ids,)).fetchall()
    return {r["wishlist_id"]: {"price_low": float(r["lo"]), "price_high": float(r["hi"]), "checks": r["n"], "checked_at": float(r["at"])} for r in rows}
