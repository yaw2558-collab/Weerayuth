"""P0-3 feedback tests: POST /feedback stores votes, GET /admin/feedback lists.

Firestore faked at the db.collection / _collection_items boundary; auth
faked at _verify (same seams as the billing tests).
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_feedback.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}


def _auth(monkeypatch):
  monkeypatch.setattr(
    main, "_verify", lambda auth: {"uid": "user1", "email": "u@x.co"}
  )


class _FakeCollection:
  def __init__(self, store):
    self._store = store

  def add(self, doc):
    self._store.append(doc)
    return (SimpleNamespace(id=f"doc{len(self._store)}"), None)


def _fake_db(monkeypatch, store):
  def _coll(name):
    assert name == "feedback", name
    return _FakeCollection(store)

  monkeypatch.setattr(main, "db", SimpleNamespace(collection=_coll))


def test_feedback_requires_auth():
  r = client.post("/feedback", json={"vote": "up", "question": "q"})
  assert r.status_code == 401


def test_feedback_rejects_bad_vote(monkeypatch):
  _auth(monkeypatch)
  r = client.post(
    "/feedback", json={"vote": "meh", "question": "q"}, headers=AUTH
  )
  assert r.status_code == 400


def test_feedback_requires_vote(monkeypatch):
  _auth(monkeypatch)
  r = client.post("/feedback", json={"question": "q"}, headers=AUTH)
  assert r.status_code == 422


def test_feedback_up_stores_row(monkeypatch):
  _auth(monkeypatch)
  store = []
  _fake_db(monkeypatch, store)
  r = client.post(
    "/feedback",
    json={
      "vote": "up",
      "question": "นำเข้าลำโพงเท่าไหร่",
      "log_id": "abc123",
      "session_id": "web-1",
    },
    headers=AUTH,
  )
  assert r.status_code == 200
  assert r.json() == {"ok": True}
  assert len(store) == 1
  row = store[0]
  assert row["user_id"] == "user1"
  assert row["vote"] == "up"
  assert row["question"] == "นำเข้าลำโพงเท่าไหร่"
  assert row["log_id"] == "abc123"
  assert row["session_id"] == "web-1"
  assert row["correct_hs"] == "" and row["comment"] == ""


def test_feedback_down_with_correction(monkeypatch):
  _auth(monkeypatch)
  store = []
  _fake_db(monkeypatch, store)
  r = client.post(
    "/feedback",
    json={
      "vote": "down",
      "question": "พิกัดไอโฟน",
      "correct_hs": "8517.13.00",
      "comment": "ควรเป็นโทรศัพท์",
      "log_id": "abc124",
    },
    headers=AUTH,
  )
  assert r.status_code == 200
  row = store[0]
  assert row["vote"] == "down"
  assert row["correct_hs"] == "8517.13.00"
  assert row["comment"] == "ควรเป็นโทรศัพท์"


def test_feedback_truncates_long_fields(monkeypatch):
  _auth(monkeypatch)
  store = []
  _fake_db(monkeypatch, store)
  r = client.post(
    "/feedback",
    json={
      "vote": "down",
      "question": "q" * 3000,
      "correct_hs": "1" * 100,
      "comment": "c" * 3000,
    },
    headers=AUTH,
  )
  assert r.status_code == 200
  row = store[0]
  assert len(row["question"]) == 2000
  assert len(row["correct_hs"]) == 64
  assert len(row["comment"]) == 2000


def test_feedback_store_failure_is_502(monkeypatch):
  _auth(monkeypatch)

  class _Boom:
    def add(self, doc):
      raise RuntimeError("firestore down")

  monkeypatch.setattr(
    main, "db", SimpleNamespace(collection=lambda name: _Boom())
  )
  r = client.post(
    "/feedback", json={"vote": "up", "question": "q"}, headers=AUTH
  )
  assert r.status_code == 502


def test_admin_feedback_rejects_bad_key(monkeypatch):
  monkeypatch.setattr(main, "ADMIN_KEY", "secret")
  assert client.get("/admin/feedback").status_code == 403
  r = client.get("/admin/feedback", headers={"x-admin-key": "wrong"})
  assert r.status_code == 403


def test_admin_feedback_lists_newest_first(monkeypatch):
  monkeypatch.setattr(main, "ADMIN_KEY", "secret")
  t1 = datetime(2026, 10, 10, 3, 14, tzinfo=timezone.utc)
  t2 = datetime(2026, 10, 11, 6, 46, tzinfo=timezone.utc)
  monkeypatch.setattr(
    main,
    "_collection_items",
    lambda name: [
      ("f1", {"user_id": "u1", "ts": t1, "vote": "up", "question": "q1"}),
      ("f2", {"user_id": "u2", "ts": t2, "vote": "down", "question": "q2",
              "correct_hs": "8517.13.00", "comment": "c2", "log_id": "L2"}),
    ],
  )
  r = client.get("/admin/feedback", headers={"x-admin-key": "secret"})
  assert r.status_code == 200
  items = r.json()["feedback"]
  assert [f["id"] for f in items] == ["f2", "f1"]  # newest first
  assert items[0]["correct_hs"] == "8517.13.00"
  assert items[0]["ts"] == t2.isoformat()
  assert items[1]["log_id"] == ""  # missing fields default to ""


def test_admin_feedback_respects_limit(monkeypatch):
  monkeypatch.setattr(main, "ADMIN_KEY", "secret")
  rows = [
    (f"f{i}", {"user_id": "u", "ts": i, "vote": "up", "question": "q"})
    for i in range(5)
  ]
  monkeypatch.setattr(main, "_collection_items", lambda name: rows)
  r = client.get("/admin/feedback?limit=2", headers={"x-admin-key": "secret"})
  assert r.status_code == 200
  assert len(r.json()["feedback"]) == 2
