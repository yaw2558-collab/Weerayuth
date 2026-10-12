"""P3 admin tests: /admin page + /admin/stats aggregates + /admin/users list."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)

FAKE = {
  "users": [{"credits": 20}, {"credits": 5}, {}],
  "payments": [
    {"status": "succeeded", "livemode": False, "amount_thb": 100, "credits": 100},
    {"status": "succeeded", "livemode": True, "amount_thb": 450, "credits": 500},
    {"status": "failed", "livemode": True, "amount_thb": 100, "credits": 0},
  ],
  "usage_logs": [
    {"est_cost_usd": 0.05, "grounding_calls": 2},
    {"est_cost_usd": 0.03, "grounding_calls": 0},
    {"est_cost_usd": 9.99, "grounding_calls": 99, "user_id": "measure-1-x"},
  ],
}


def test_admin_page_serves():
  r = client.get("/admin")
  assert r.status_code == 200
  assert "admin" in r.text.lower()
  assert "รายชื่อผู้ใช้" in r.text  # per-user table section
  assert "/admin/users" in r.text


def test_logo_serves():
  r = client.get("/logo.svg")
  assert r.status_code == 200
  assert r.headers["content-type"] == "image/svg+xml"
  assert "<svg" in r.text


def test_stats_rejects_bad_key(monkeypatch):
  monkeypatch.setattr(main, "ADMIN_KEY", "secret")
  assert client.get("/admin/stats").status_code == 403
  r = client.get("/admin/stats", headers={"x-admin-key": "wrong"})
  assert r.status_code == 403


def test_stats_aggregates(monkeypatch):
  monkeypatch.setattr(main, "ADMIN_KEY", "secret")
  monkeypatch.setattr(main, "_collection_docs", lambda name: FAKE[name])
  r = client.get("/admin/stats", headers={"x-admin-key": "secret"})
  assert r.status_code == 200
  assert r.json() == {
    "users": 3,
    "credits_outstanding": 25,
    "payments_succeeded": 2,
    "payments_failed": 1,
    "revenue_thb": 550,
    "revenue_live_thb": 450,
    "credits_sold": 600,
    "queries": 2,
    "est_cost_usd": 0.08,
    "grounding_calls": 2,
  }


def test_users_rejects_bad_key(monkeypatch):
  monkeypatch.setattr(main, "ADMIN_KEY", "secret")
  assert client.get("/admin/users").status_code == 403
  r = client.get("/admin/users", headers={"x-admin-key": "wrong"})
  assert r.status_code == 403


def test_users_lists_per_user_totals(monkeypatch):
  monkeypatch.setattr(main, "ADMIN_KEY", "secret")
  t1 = datetime(2026, 10, 10, 3, 14, tzinfo=timezone.utc)
  t2 = datetime(2026, 10, 11, 6, 46, tzinfo=timezone.utc)
  monkeypatch.setattr(
    main,
    "_collection_items",
    lambda name: [
      ("u1", {"email": "a@x.co", "credits": 20, "created": t1}),
      ("u2", {"email": "b@x.co", "credits": 90, "created": t2}),
      ("u3", {"email": "c@x.co", "credits": 30, "created": None}),
    ],
  )
  monkeypatch.setattr(
    main,
    "_collection_docs",
    lambda name: [
      {
        "user_id": "u1",
        "est_cost_usd": 1.05,
        "grounding_calls": 28,
        "ts": t1,
      },
      {
        "user_id": "u1",
        "est_cost_usd": 0.11,
        "grounding_calls": 2,
        "ts": t2,
      },
      {
        "user_id": "measure-1-x",
        "est_cost_usd": 9.99,
        "grounding_calls": 99,
        "ts": t2,
      },
    ],
  )
  r = client.get("/admin/users", headers={"x-admin-key": "secret"})
  assert r.status_code == 200
  users = r.json()["users"]
  assert [u["uid"] for u in users] == ["u1", "u2", "u3"]  # active first
  assert users[0]["email"] == "a@x.co"
  assert users[0]["queries"] == 2
  assert users[0]["est_cost_usd"] == 1.16
  assert users[0]["grounding_calls"] == 30
  assert users[0]["last_ts"] == t2.isoformat()
  assert users[0]["created"] == t1.isoformat()
  assert users[1]["queries"] == 0 and users[1]["last_ts"] is None
  assert all(u["uid"] != "measure-1-x" for u in users)
