"""Frontend regression tests for the served index.html.

Leading/trailing spaces in the email box (mobile autocomplete, copy-paste)
make Firebase reject signup/login with auth/invalid-email, so the page must
trim the email before calling Firebase Auth.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)


def _index_html():
  r = client.get("/")
  assert r.status_code == 200
  return r.text


def test_email_auth_trims_email():
  html = _index_html()
  assert "email.value.trim()" in html
  assert "signInWithEmailAndPassword(email.value" not in html
  assert "createUserWithEmailAndPassword(email.value" not in html
