"""Speed-sprint chat tests: JSON + SSE responses and the answer cache.

Seams faked at the boundary: _verify, _get_or_create_user, _check_rate,
runner.run_async, _cache_get/_cache_put, _charge_and_log.
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_chat.py
"""

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}
SSE = {"Authorization": "Bearer [REDACTED]", "Accept": "text/event-stream"}


def _auth(monkeypatch, credits=30, consent=True):
  monkeypatch.setattr(
    main, "_verify", lambda auth: {"uid": "user1", "email": "u@x.co"}
  )
  user = {"credits": credits}
  if consent:
    user["consent_ts"] = "yes"
  monkeypatch.setattr(main, "_get_or_create_user", lambda uid, email: user)
  monkeypatch.setattr(main, "_check_rate", lambda uid: None)
  monkeypatch.setattr(main, "_cache_get", lambda key: None)


def _ev(text, partial=False, usage=None, grounding=False):
  return SimpleNamespace(
    content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
    partial=partial,
    usage_metadata=usage,
    grounding_metadata={} if grounding else None,
  )


def _fake_run(events):
  async def _gen(**kw):
    for e in events:
      yield e

  return _gen


def _usage():
  return SimpleNamespace(
    prompt_token_count=100, candidates_token_count=50, thoughts_token_count=0
  )


def _parse_sse(body):
  events = []
  for chunk in body.split("\n\n"):
    ev, data = None, None
    for line in chunk.splitlines():
      if line.startswith("event:"):
        ev = line[6:].strip()
      elif line.startswith("data:"):
        data = json.loads(line[5:].strip())
    if ev:
      events.append((ev, data))
  return events


def test_normalize_and_key_stable():
  assert (
    main._normalize_question("  นำเข้า   ลำโพง\nบลูทูธ\t ")
    == "นำเข้า ลำโพง บลูทูธ"
  )
  k1 = main._cache_key(main._normalize_question("ถาม HS"))
  k2 = main._cache_key(main._normalize_question("  ถาม   hs "))
  assert k1 == k2
  assert len(k1) == 64
  assert main._cache_key("อื่น") != k1


def test_chat_json_returns_answer_and_charges(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main.runner,
    "run_async",
    _fake_run([_ev("สวัสดี", partial=True), _ev("พิกัด 8518", usage=_usage())]),
  )
  puts, charges = [], []

  def fake_charge(uid, sid, message, answer, usage, attachment, cached=False):
    charges.append((uid, answer, usage, cached))
    return 20

  monkeypatch.setattr(main, "_charge_and_log", fake_charge)
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: puts.append((k, a, u)))

  r = client.post("/chat", data={"message": "hi"}, headers=AUTH)
  assert r.status_code == 200
  d = r.json()
  assert d["answer"] == "พิกัด 8518" + main.FOOTER  # partials not in final
  assert d["credits_left"] == 20
  assert d["usage"]["prompt_tokens"] == 100
  assert d["usage"]["candidates_tokens"] == 50
  assert d["session_id"].startswith("web-")
  assert len(puts) == 1 and puts[0][1] == "พิกัด 8518"  # raw cached, no footer
  assert charges[0][0] == "user1" and charges[0][3] is False


def test_chat_sse_streams_tokens_then_done(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main.runner,
    "run_async",
    _fake_run([_ev("สวัสดี", partial=True), _ev("พิกัด 8518", usage=_usage())]),
  )
  monkeypatch.setattr(
    main, "_charge_and_log", lambda *a, **k: 20
  )
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post("/chat", data={"message": "hi"}, headers=SSE)
  assert r.status_code == 200
  assert r.headers["content-type"].startswith("text/event-stream")
  events = _parse_sse(r.text)
  assert events[0][0] == "stage"  # sign of life before first token
  assert ("token", {"text": "สวัสดี"}) in events
  assert events[-1][0] == "done"
  done = events[-1][1]
  assert done["answer"] == "พิกัด 8518" + main.FOOTER
  assert done["credits_left"] == 20
  assert done["usage"]["prompt_tokens"] == 100


def test_chat_cache_hit_skips_runner_json_and_sse(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main,
    "_cache_get",
    lambda key: {"answer": "cached-raw", "usage": {}, "ts": time.time()},
  )

  def _boom(**kw):
    raise AssertionError("runner must not run on cache hit")

  monkeypatch.setattr(main.runner, "run_async", _boom)
  charges = []

  def fake_charge(uid, sid, message, answer, usage, attachment, cached=False):
    charges.append(cached)
    return 20

  monkeypatch.setattr(main, "_charge_and_log", fake_charge)

  r = client.post("/chat", data={"message": "ถามซ้ำ"}, headers=AUTH)
  assert r.status_code == 200
  d = r.json()
  assert d["answer"] == "cached-raw" + main.FOOTER
  assert d["usage"]["cached"] is True
  assert d["usage"]["latency_s"] == 0.0

  r = client.post("/chat", data={"message": "ถามซ้ำ"}, headers=SSE)
  assert r.status_code == 200
  events = _parse_sse(r.text)
  assert [e for e, _ in events] == ["done"]
  assert events[0][1]["answer"] == "cached-raw" + main.FOOTER
  assert charges == [True, True]


def test_chat_cache_hit_insufficient_credits(monkeypatch):
  _auth(monkeypatch, credits=30)
  monkeypatch.setattr(
    main,
    "_cache_get",
    lambda key: {"answer": "x", "usage": {}, "ts": time.time()},
  )
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: None)

  r = client.post("/chat", data={"message": "ถามซ้ำ"}, headers=AUTH)
  assert r.status_code == 402


def test_chat_requires_consent(monkeypatch):
  _auth(monkeypatch, consent=False)
  r = client.post("/chat", data={"message": "hi"}, headers=AUTH)
  assert r.status_code == 403


def test_chat_sse_agent_error_yields_error_event(monkeypatch):
  _auth(monkeypatch)

  async def _failing(**kw):
    yield _ev("เริ่ม", partial=True)
    raise RuntimeError("vertex 500")

  monkeypatch.setattr(main.runner, "run_async", _failing)
  charges = []
  monkeypatch.setattr(
    main, "_charge_and_log", lambda *a, **k: charges.append(1) or 20
  )
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post("/chat", data={"message": "hi"}, headers=SSE)
  assert r.status_code == 200
  events = _parse_sse(r.text)
  assert events[0][0] == "stage"
  assert ("token", {"text": "เริ่ม"}) in events
  assert events[-1][0] == "error"
  assert charges == []  # failures are not charged


def test_answer_footer_has_contact_email():
  assert "mailto:yaw2558@gmail.com" in main.FOOTER
