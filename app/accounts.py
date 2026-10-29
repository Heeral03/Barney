"""Moving what a visitor did before signing in over to their new account."""
import logging

from app.db import pool
from app.memory import store as ltm_store

log = logging.getLogger(__name__)


def claim_guest(guest_id: str, user_id: str) -> dict:
    """Re-key a guest's chats, wishlist, budget and memories to `user_id`. What the account already has wins on a clash."""
    with pool.connection() as conn, conn.transaction():
        conn.execute("update chat_log set user_id = %s where user_id = %s", (user_id, guest_id))
        conn.execute("delete from wishlist g using wishlist u where g.user_id = %s and u.user_id = %s and g.key = u.key",
                     (guest_id, user_id))
        moved = conn.execute("update wishlist set user_id = %s where user_id = %s returning id", (user_id, guest_id)).fetchall()
        conn.execute("update budget set user_id = %s where user_id = %s "
                     "and not exists (select 1 from budget where user_id = %s)", (user_id, guest_id, user_id))
        conn.execute("delete from budget where user_id = %s", (guest_id,))
    memories = 0
    for m in ltm_store.all_memories(ltm_store.ltm, guest_id):
        if not ltm_store.ltm.get(ltm_store._ns(user_id), m["key"]):
            ltm_store.ltm.put(ltm_store._ns(user_id), m["key"], {k: v for k, v in m.items() if k != "key"})
            memories += 1
        ltm_store.forget(ltm_store.ltm, guest_id, m["key"])
    log.info("claimed guest data: %d wishlist items, %d memories", len(moved), memories)
    return {"claimed": True, "wishlist": len(moved), "memories": memories}
