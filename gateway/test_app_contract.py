"""App contract: /me + /consent shape the ThaiCustoms app relies on.

Locks existing behavior (no prod change) so the Phase 2 app build has a
tested contract for credits display + the consent gate.
Run from thai-customs/: ..\.venv\Scripts\python -m pytest gateway/test_app_contract.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}


def test_me_requires_auth():
  r = client.get("/me")
  assert r.status_code == 401


def test_me_returns_app_shape(monkeypatch):
  monkeypatch.setattr(
    main, "_verify", lambda auth: {"uid": "u1", "email": "a@b.c"}
  )
  monkeypatch.setattr(
    main, "_get_or_create_user",
    lambda uid, email: {"credits": 70, "consent_ts": "TS"},
  )
  r = client.get("/me", headers=AUTH)
  assert r.status_code == 200
  assert r.json() == {
    "uid": "u1", "email": "a@b.c", "credits": 70, "consent_ts": "TS",
  }


def test_consent_requires_auth():
  r = client.post("/consent")
  assert r.status_code == 401


def test_consent_writes_timestamp(monkeypatch):
  monkeypatch.setattr(main, "_verify", lambda auth: {"uid": "u1"})
  monkeypatch.setattr(main, "_get_or_create_user", lambda uid, email: {})
  updates = []

  class Ref:
    def update(self, data):
      updates.append(data)

  monkeypatch.setattr(main, "_user_ref", lambda uid: Ref())
  r = client.post("/consent", headers=AUTH)
  assert r.status_code == 200
  assert r.json() == {"ok": True}
  assert len(updates) == 1 and "consent_ts" in updates[0]
