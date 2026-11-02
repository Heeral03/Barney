"""Reviewer queue: negative feedback -> labelled by a human -> exported as eval cases."""
import json
import uuid

import pytest

from app import history, review, signals
from app.db import pool
from tests.conftest import client_for


@pytest.fixture
def shopper():
    uid = f"test-{uuid.uuid4().hex[:8]}"
    yield uid
    with pool.connection() as conn:
        conn.execute("delete from feedback where user_id = %s", (uid,))
        conn.execute("delete from chat_log where user_id = %s", (uid,))


def mine(items, uid_thread):
    return [i for i in items if i["request"].startswith(uid_thread)]


def test_the_queue_has_negative_feedback_with_the_shoppers_request(shopper):
    thread = f"t-{shopper}"
    history.append(thread, shopper, [("user", f"{shopper} running shoes for women", {}), ("assistant", "Here you go", {}),
                                     ("user", "Show me other options", {})])
    signals.add_feedback(shopper, thread, "running shoes", "Men's Runner X", "wrong")
    signals.add_feedback(shopper, thread, "running shoes", "Women's Runner Y", "up")  # praise is not reviewed
    items = mine(review.queue(500), shopper)
    assert len(items) == 1 and items[0]["title"] == "Men's Runner X" and items[0]["verdict"] == "wrong"
    assert items[0]["request"] == f"{shopper} running shoes for women", "button presses are left out of the request"


def test_labelling_removes_it_from_the_queue_and_cannot_be_repeated(shopper):
    thread = f"t-{shopper}"
    history.append(thread, shopper, [("user", f"{shopper} headphones", {})])
    signals.add_feedback(shopper, thread, "headphones", "Micro USB Headphones", "down")
    item = mine(review.queue(500), shopper)[0]
    assert review.label(item["id"], "should_exclude", "wrong connector", "reviewer-1")
    assert not review.label(item["id"], "acceptable", "", "reviewer-2"), "the first decision stands"
    assert mine(review.queue(500), shopper) == []
    with pytest.raises(ValueError):
        review.label(item["id"], "maybe")


def test_export_appends_only_new_reviewed_cases(shopper, tmp_path):
    thread = f"t-{shopper}"
    history.append(thread, shopper, [("user", f"{shopper} phone", {})])
    signals.add_feedback(shopper, thread, "phone", "Old Phone 4G", "wrong")
    review.label(mine(review.queue(500), shopper)[0]["id"], "should_exclude", "outdated", "r")
    path = tmp_path / "reviewed.jsonl"
    assert review.export(path) >= 1
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mine_rows = [r for r in rows if r["title"] == "Old Phone 4G"]
    assert len(mine_rows) == 1 and mine_rows[0]["label"] == "should_exclude" and mine_rows[0]["fixed"] is False
    assert mine_rows[0]["source"] == "feedback" and mine_rows[0]["request"] == f"{shopper} phone"
    assert review.export(path) == 0, "running it again adds nothing"


def test_the_admin_endpoints_are_for_admins_only(shopper, monkeypatch):
    thread = f"t-{shopper}"
    history.append(thread, shopper, [("user", f"{shopper} laptop", {})])
    signals.add_feedback(shopper, thread, "laptop", "Ancient Laptop", "down")
    client = client_for(f"guest:{shopper}")
    monkeypatch.setenv("ADMIN_USERS", "someone-else")
    assert client.get("/admin/review").status_code == 403
    assert client.post("/admin/review/1", json={"label": "acceptable"}).status_code == 403

    monkeypatch.setenv("ADMIN_USERS", f"guest:{shopper}")
    items = mine(client.get("/admin/review?limit=200").json()["items"], shopper)
    assert len(items) == 1
    assert client.post(f"/admin/review/{items[0]['id']}", json={"label": "nonsense"}).status_code == 400
    assert client.post(f"/admin/review/{items[0]['id']}", json={"label": "should_exclude", "note": "too old"}).json() == {"ok": True}
    assert client.post(f"/admin/review/{items[0]['id']}", json={"label": "acceptable"}).status_code == 404, "already reviewed"
