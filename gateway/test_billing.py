"""P2 billing tests: packages, checkout, webhook.

Webhook signature is verified for real (HMAC-signed payloads); Firestore is
faked at the _payment_exists/_grant_credits/_record_payment boundary.
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_billing.py
"""

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)
WEBHOOK_SECRET = "whsec_test_123"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
  t = int(time.time())
  sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
  return f"t={t},v1={sig}"


def _completed_event(session_id="cs_test_123", paid=True, credits="100"):
  return {
    "id": "evt_test_1",
    "object": "event",
    "type": "checkout.session.completed",
    "data": {
      "object": {
        "id": session_id,
        "object": "checkout.session",
        "payment_status": "paid" if paid else "unpaid",
        "amount_total": 10000,
        "metadata": {"uid": "user1", "credits": credits, "price_id": "price_x"},
      }
    },
  }


def test_packages_lists_three():
  r = client.get("/billing/packages")
  assert r.status_code == 200
  pkgs = r.json()["packages"]
  assert sorted(p["credits"] for p in pkgs) == [100, 500, 1000]
  assert all(p["price_id"] and p["thb"] for p in pkgs)


def test_checkout_requires_auth():
  pid = next(iter(main.STRIPE_PRICES))
  r = client.post("/billing/checkout", json={"price_id": pid})
  assert r.status_code == 401


def test_checkout_rejects_unknown_price(monkeypatch):
  monkeypatch.setattr(main, "_verify", lambda auth: {"uid": "user1"})
  r = client.post(
    "/billing/checkout",
    json={"price_id": "price_nope"},
    headers={"Authorization": "Bearer x"},
  )
  assert r.status_code == 400


def test_checkout_creates_session(monkeypatch):
  monkeypatch.setattr(main, "_verify", lambda auth: {"uid": "user1"})
  monkeypatch.setattr(main, "STRIPE_SECRET_KEY", "sk_test_fake")
  calls = {}

  class FakeSession:
    url = "https://checkout.stripe.com/pay/cs_test"

  def fake_create(**kw):
    calls.update(kw)
    return FakeSession()

  monkeypatch.setattr("stripe.checkout.Session.create", fake_create)
  pid = next(iter(main.STRIPE_PRICES))
  r = client.post(
    "/billing/checkout",
    json={"price_id": pid},
    headers={"Authorization": "Bearer x"},
  )
  assert r.status_code == 200
  assert r.json()["url"].startswith("https://checkout.stripe.com/")
  assert calls["metadata"]["uid"] == "user1"
  assert calls["metadata"]["credits"] == main.STRIPE_PRICES[pid]["credits"]
  assert calls["line_items"] == [{"price": pid, "quantity": 1}]
  thb = main.STRIPE_PRICES[pid]["thb"]
  assert calls["success_url"].endswith(f"?topup=success&thb={thb}")


def test_webhook_rejects_bad_signature(monkeypatch):
  monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
  r = client.post(
    "/billing/webhook",
    content=b'{"type":"x"}',
    headers={"stripe-signature": "t=1,v1=deadbeef"},
  )
  assert r.status_code == 400
  r = client.post("/billing/webhook", content=b"{}")
  assert r.status_code == 400


def test_webhook_grants_credits(monkeypatch):
  monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
  monkeypatch.setattr(main, "_payment_exists", lambda sid: False)
  grants, payments = [], []

  def fake_grant(uid, credits, reason):
    grants.append((uid, credits, reason))
    return 130

  monkeypatch.setattr(main, "_grant_credits", fake_grant)
  monkeypatch.setattr(main, "_record_payment", lambda sid, d: payments.append((sid, d)))

  payload = json.dumps(_completed_event()).encode()
  r = client.post(
    "/billing/webhook", content=payload, headers={"stripe-signature": _sign(payload)}
  )
  assert r.status_code == 200
  assert r.json() == {"received": True}
  assert grants == [("user1", 100, "topup:stripe:cs_test_123")]
  assert payments[0][0] == "cs_test_123"
  assert payments[0][1]["status"] == "succeeded"
  assert payments[0][1]["credits"] == 100
  assert payments[0][1]["livemode"] is False


def test_webhook_duplicate_ignored(monkeypatch):
  monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
  monkeypatch.setattr(main, "_payment_exists", lambda sid: True)
  grants = []
  monkeypatch.setattr(main, "_grant_credits", lambda *a: grants.append(a) or 0)
  monkeypatch.setattr(main, "_record_payment", lambda sid, d: None)

  payload = json.dumps(_completed_event()).encode()
  r = client.post(
    "/billing/webhook", content=payload, headers={"stripe-signature": _sign(payload)}
  )
  assert r.status_code == 200
  assert grants == []


def test_webhook_unpaid_records_failed(monkeypatch):
  monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
  monkeypatch.setattr(main, "_payment_exists", lambda sid: False)
  grants, payments = [], []
  monkeypatch.setattr(main, "_grant_credits", lambda *a: grants.append(a) or 0)
  monkeypatch.setattr(main, "_record_payment", lambda sid, d: payments.append((sid, d)))

  payload = json.dumps(_completed_event(paid=False)).encode()
  r = client.post(
    "/billing/webhook", content=payload, headers={"stripe-signature": _sign(payload)}
  )
  assert r.status_code == 200
  assert grants == []
  assert payments[0][1]["status"] == "failed"


def test_webhook_ignores_other_events(monkeypatch):
  monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
  grants = []
  monkeypatch.setattr(main, "_grant_credits", lambda *a: grants.append(a) or 0)

  payload = json.dumps({"id": "e", "object": "event", "type": "payment_intent.created",
                        "data": {"object": {}}}).encode()
  r = client.post(
    "/billing/webhook", content=payload, headers={"stripe-signature": _sign(payload)}
  )
  assert r.status_code == 200
  assert grants == []
