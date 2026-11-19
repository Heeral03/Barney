"""Per-account settings: whether Barney may keep learning, whether onboarding is done, and the shopping profiles
("me", "Mom", "Gift for Riya") that keep one person's tastes from mixing with another's."""
import re

from app import region
from app.db import pool

with pool.connection() as conn:
    conn.execute("""
        create table if not exists user_settings (
            user_id text primary key,
            learning boolean not null default true,
            onboarded boolean not null default false
        )""")
    conn.execute("alter table user_settings add column if not exists country text")
    conn.execute("create table if not exists profiles (user_id text not null, name text not null, primary key (user_id, name))")

MAX_PROFILES = 8
ME = "me"


def get(user_id: str) -> dict:
    with pool.connection() as conn:
        row = conn.execute("select learning, onboarded, country from user_settings where user_id = %s", (user_id,)).fetchone()
        names = [r["name"] for r in conn.execute("select name from profiles where user_id = %s order by name", (user_id,)).fetchall()]
    return {"learning": row["learning"] if row else True, "onboarded": row["onboarded"] if row else False, "profiles": [ME, *names],
            "country": (row["country"] if row else None) or None}


def learning_on(user_id: str) -> bool:
    return get(user_id)["learning"]


def update(user_id: str, learning: bool | None = None, onboarded: bool | None = None, country: str | None = None) -> dict:
    with pool.connection() as conn:
        conn.execute("insert into user_settings (user_id) values (%s) on conflict do nothing", (user_id,))
        if learning is not None:
            conn.execute("update user_settings set learning = %s where user_id = %s", (learning, user_id))
        if onboarded is not None:
            conn.execute("update user_settings set onboarded = %s where user_id = %s", (onboarded, user_id))
        if country is not None:  # "" clears the choice, so the detected country applies again
            conn.execute("update user_settings set country = %s where user_id = %s", (region.normalize(country) or None, user_id))
    return get(user_id)


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[#\n\r]", " ", name or "")).strip()[:30]


def add_profile(user_id: str, name: str) -> dict:
    name = clean_name(name)
    if not name or name.lower() == ME:
        return get(user_id)
    if len(get(user_id)["profiles"]) <= MAX_PROFILES:
        with pool.connection() as conn:
            conn.execute("insert into profiles (user_id, name) values (%s, %s) on conflict do nothing", (user_id, name))
    return get(user_id)


def remove_profile(user_id: str, name: str) -> dict:
    with pool.connection() as conn:
        conn.execute("delete from profiles where user_id = %s and name = %s", (user_id, name))
    return get(user_id)


def memory_id(user_id: str, profile: str | None) -> str:
    """Whose tastes are in play: the account's own ("me"), or one of its profiles. An unknown profile falls back to "me"."""
    name = clean_name(profile or "")
    if not name or name.lower() == ME or name not in get(user_id)["profiles"]:
        return user_id
    return f"{user_id}#{name}"
