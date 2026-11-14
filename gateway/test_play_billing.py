"""Play Billing tests: products list + purchase-token verify.

The Play Developer API is faked at the _fetch_play_purchase boundary and
Firestore at the _payment_exists/_grant_credits/_record_payment boundary.
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_play_billing.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main
import gateway.play_billing as play

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}


def _fake_purchase(monkeypatch, **over):
  p = {"orderId": "GPA.1234-5678-9012-34567", "purchaseState": 0,
       "productId": "credits_100"}
  p.update(over)
  monkeypatch.setattr(play, "_fetch_play_purchase", lambda pid, tok: p)
  return p


def _wired(monkeypatch, payments_exist=False, balance=0):
  monkeypatch.setattr(main, "_verify", lambda auth: {"uid": "user1"})
  monkeypatch.setattr(main, "_payment_exists", lambda sid: payments_exist)
  grants, records = [], []
  monkeypatch.setattr(
    main, "_grant_credits",
    lambda uid, credits, reason: grants.append((uid, credits, reason)) or balance + credits,
  )
  monkeypatch.setattr(
    main, "_record_payment", lambda sid, data: records.append((sid, data))
  )
  monkeypatch.setattr(
    main, "_get_or_create_user", lambda uid, email: {"credits": balance}
  )
  return grants, records


def test_play_products_lists_three():
  r = client.get("/billing/play/products")
  assert r.status_code == 200
  pkgs = r.json()["products"]
  assert sorted(p["credits"] for p in pkgs) == [100, 500, 1000]
  assert sorted(p["product_id"] for p in pkgs) == [
    "credits_100", "credits_1000", "credits_500"]
  assert all(p["thb"] for p in pkgs)


def test_play_verify_requires_auth():
  r = client.post("/billing/play/verify",
                  json={"product_id": "credits_100", "purchase_token": "x"})
  assert r.status_code == 401


def test_play_verify_rejects_unknown_product(monkeypatch):
  monkeypatch.setattr(main, "_verify", lambda auth: {"uid": "user1"})
  r = client.post("/billing/play/verify",
                  json={"product_id": "nope", "purchase_token": "x"},
                  headers=AUTH)
  assert r.status_code == 400


def test_play_verify_grants_credits(monkeypatch):
  _fake_purchase(monkeypatch)
  grants, records = _wired(monkeypatch)
  r = client.post("/billing/play/verify",
                  json={"product_id": "credits_100", "purchase_token": "tok"},
                  headers=AUTH)
  assert r.status_code == 200
  assert r.json() == {"ok": True, "credits": 100, "balance": 100}
  assert grants == [("user1", 100, "topup:play:GPA.1234-5678-9012-34567")]
  sid, data = records[0]
  assert sid == "GPA.1234-5678-9012-34567"
  assert data["provider"] == "play" and data["status"] == "succeeded"
  assert data["livemode"] is True and data["credits"] == 100


def test_play_verify_duplicate_is_idempotent(monkeypatch):
  _fake_purchase(monkeypatch)
  grants, records = _wired(monkeypatch, payments_exist=True, balance=55)
  r = client.post("/billing/play/verify",
                  json={"product_id": "credits_100", "purchase_token": "tok"},
                  headers=AUTH)
  assert r.status_code == 200
  assert r.json() == {"ok": True, "duplicate": True, "balance": 55}
  assert grants == [] and records == []


def test_play_verify_rejects_unfinished_purchase(monkeypatch):
  _fake_purchase(monkeypatch, purchaseState=1)  # pending
  grants, records = _wired(monkeypatch)
  r = client.post("/billing/play/verify",
                  json={"product_id": "credits_100", "purchase_token": "tok"},
                  headers=AUTH)
  assert r.status_code == 400
  assert grants == [] and records == []


def test_play_verify_rejects_missing_order(monkeypatch):
  p = _fake_purchase(monkeypatch)
  del p["orderId"]
  grants, records = _wired(monkeypatch)
  r = client.post("/billing/play/verify",
                  json={"product_id": "credits_100", "purchase_token": "tok"},
                  headers=AUTH)
  assert r.status_code == 400
  assert grants == []


def test_play_verify_test_purchase_not_live_revenue(monkeypatch):
  _fake_purchase(monkeypatch, purchaseType=0)  # license-tester sandbox
  grants, records = _wired(monkeypatch)
  r = client.post("/billing/play/verify",
                  json={"product_id": "credits_100", "purchase_token": "tok"},
                  headers=AUTH)
  assert r.status_code == 200
  assert records[0][1]["livemode"] is False
  assert grants[0][1] == 100  # tester still gets the credits


def test_play_verify_unconfigured_without_key(monkeypatch):
  monkeypatch.setattr(main, "_verify", lambda auth: {"uid": "user1"})
  monkeypatch.delenv("PLAY_SERVICE_ACCOUNT_JSON", raising=False)
  r = client.post("/billing/play/verify",
                  json={"product_id": "credits_100", "purchase_token": "tok"},
                  headers=AUTH)
  assert r.status_code == 500
