"""Query-history tests: full answers are stored per usage row and the
owner can list them back (newest first) for re-reading. Free vague
clarifications are not history — they never had a real answer.

Seams faked at the boundary: _verify, _user_usage.
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_history.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}


def _auth(monkeypatch, uid="user1"):
  monkeypatch.setattr(
    main, "_verify", lambda auth: {"uid": uid, "email": "u@x.co"}
  )


def _row(question, answer, day, **extra):
  r = {
    "user_id": "user1",
    "question": question,
    "answer": answer,
    "ts": datetime(2026, 10, day, 2, 0, tzinfo=timezone.utc),
    "cached": False,
  }
  r.update(extra)
  return r


def test_usage_row_stores_answer():
  usage = {
    "prompt_tokens": 1,
    "candidates_tokens": 2,
    "thoughts_tokens": 0,
    "grounding_calls": 3,
    "latency_s": 9.9,
    "est_cost_usd": 0.5,
    "capped": False,
  }
  row = main._usage_row("u", "s", "q?", "a!" * 500, usage, None)
  assert row["answer"] == "a!" * 500  # full text, not just chars
  assert row["question"] == "q?"


def test_history_requires_auth():
  assert client.get("/history").status_code == 401


def test_history_returns_own_newest_first(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main,
    "_user_usage",
    lambda uid: [
      _row("q-old", "a-old", 10),
      _row("q-new", "a-new", 12),
      _row("q-vague", "clarify-template", 11, free_reason="vague_clarify"),
      _row("q-mid", "", 11),  # pre-history row: answer backfilled empty
    ],
  )
  r = client.get("/history", headers=AUTH)
  assert r.status_code == 200
  h = r.json()["history"]
  assert [e["question"] for e in h] == ["q-new", "q-mid", "q-old"]
  assert h[0]["answer"] == "a-new"
  assert h[1]["answer"] == ""
  assert "ts" in h[0] and h[0]["cached"] is False


def test_history_scoped_to_caller(monkeypatch):
  _auth(monkeypatch, uid="user9")
  seen = []
  monkeypatch.setattr(
    main, "_user_usage", lambda uid: seen.append(uid) or []
  )
  r = client.get("/history", headers=AUTH)
  assert r.status_code == 200
  assert r.json() == {"history": []}
  assert seen == ["user9"]


def test_history_limit(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main,
    "_user_usage",
    lambda uid: [_row(f"q{i}", f"a{i}", 12) for i in range(40)],
  )
  r = client.get("/history", headers=AUTH)
  assert r.status_code == 200
  assert len(r.json()["history"]) == main.HISTORY_LIMIT == 30
