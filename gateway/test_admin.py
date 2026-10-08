"""P3 admin tests: /admin page + /admin/stats aggregates."""
import sys
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
  ],
}


def test_admin_page_serves():
  r = client.get("/admin")
  assert r.status_code == 200
  assert "admin" in r.text.lower()


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
