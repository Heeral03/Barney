"""Plain product numbers: where people drop off, how often a search finds nothing, how long it takes to get an answer.

Events are stored with the account id (no names, no email) so a funnel can be counted per person, and read through
`summary()` by an admin only (ADMIN_USERS in .env).
"""
import logging
from psycopg.types.json import Jsonb

from app.db import pool

log = logging.getLogger(__name__)
CLIENT_EVENTS = {"form_submitted", "form_skipped", "card_open", "share_created", "onboarding_done"}

with pool.connection() as conn:
    conn.execute("""
        create table if not exists analytics (
            id bigserial primary key,
            user_id text not null,
            name text not null,
            props jsonb not null default '{}',
            at timestamptz not null default now()
        )""")
    conn.execute("create index if not exists analytics_name_idx on analytics (name, at)")


def track(user_id: str, name: str, **props) -> None:
    try:
        with pool.connection() as conn:
            conn.execute("insert into analytics (user_id, name, props) values (%s, %s, %s)", (user_id, name, Jsonb(props)))
    except Exception as e:  # numbers must never break a shopper's turn
        log.warning("could not record %s: %s", name, e)


def summary(days: int = 30) -> dict:
    with pool.connection() as conn:
        count = lambda name: conn.execute("select count(*) as n from analytics where name = %s and at > now() - make_interval(days => %s)", (name, days)).fetchone()["n"]
        kinds = {r["k"]: r["n"] for r in conn.execute(
            "select props->>'kind' as k, count(*) as n from analytics where name = 'turn' and at > now() - make_interval(days => %s) group by 1",
            (days,)).fetchall()}
        timing = conn.execute(
            "select percentile_cont(0.5) within group (order by (props->>'first_ms')::float) as first_ms, "
            "percentile_cont(0.5) within group (order by (props->>'total_ms')::float) as total_ms "
            "from analytics where name = 'turn' and props->>'kind' = 'results' and at > now() - make_interval(days => %s)", (days,)).fetchone()
        people = conn.execute("select count(distinct user_id) as n from analytics where at > now() - make_interval(days => %s)", (days,)).fetchone()["n"]
        verdicts = {r["verdict"]: r["n"] for r in conn.execute("select verdict, count(*) as n from feedback where at > now() - make_interval(days => %s) group by 1", (days,)).fetchall()}
    shown, submitted, skipped = kinds.get("form", 0), count("form_submitted"), count("form_skipped")
    searches = kinds.get("results", 0) + kinds.get("empty", 0)
    return {
        "days": days, "people": people, "turns": sum(kinds.values()), "by_kind": kinds,
        "questionnaire": {"shown": shown, "submitted": submitted, "skipped": skipped,
                          "left_without_answering": max(0, shown - submitted - skipped)},
        "empty_search_rate": round(kinds.get("empty", 0) / searches, 3) if searches else None,
        "median_seconds_to_first_status": round((timing["first_ms"] or 0) / 1000, 2) if timing["first_ms"] is not None else None,
        "median_seconds_to_answer": round((timing["total_ms"] or 0) / 1000, 2) if timing["total_ms"] is not None else None,
        "card_opens": count("card_open"), "feedback": verdicts,
    }
