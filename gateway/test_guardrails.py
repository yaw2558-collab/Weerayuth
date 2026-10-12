"""Guardrail tests: vague-question free path, truthful grounding count, breaker.

Seams faked at the boundary: _verify, _get_or_create_user, _check_rate,
runner.run_async, _cache_get/_cache_put, _charge_and_log, _log_free_query.
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_guardrails.py
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}
SSE = {"Authorization": "Bearer [REDACTED]", "Accept": "text/event-stream"}
REAL_Q = "นำเข้าลำโพงบลูทูธจากจีน เสียอากรเท่าไหร่"


def _auth(monkeypatch, credits=30):
  monkeypatch.setattr(
    main, "_verify", lambda auth: {"uid": "user1", "email": "u@x.co"}
  )
  monkeypatch.setattr(
    main,
    "_get_or_create_user",
    lambda uid, email: {"credits": credits, "consent_ts": "yes"},
  )
  monkeypatch.setattr(main, "_check_rate", lambda uid: None)
  monkeypatch.setattr(main, "_cache_get", lambda key: None)


def _ev(text, partial=False, queries=None):
  gm = None
  if queries is not None:
    gm = SimpleNamespace(web_search_queries=list(queries))
  return SimpleNamespace(
    content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
    partial=partial,
    usage_metadata=None,
    grounding_metadata=gm,
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


def test_vague_detector_table():
  vague = [
    "พิกัดศุลกากร",  # the Oct-10 $1.05 spiral
    "HS code",
    "hi",
    "สวัสดีครับ",
    "เช็คพิกัด HS",
    "ขอพิกัดหน่อย",
    "?",
    "ยา",
    "Form E",
    "ถามหน่อย",
    "the bag",
  ]
  not_vague = [
    REAL_Q,
    "8507",
    "พิกัด 8518.21",
    "Form E ใช้ยังไง",
    "พิกัดเสื้อผ้า",
    "รองเท้า",
    "RCEP ลดอากรให้สินค้าอะไรบ้าง",
    "คำถามซ้ำสำหรับทดสอบแคช",
    "laptop charger import duty rate?",
  ]
  for q in vague:
    assert main._is_vague_question(q) is True, q
  for q in not_vague:
    assert main._is_vague_question(q) is False, q


def test_vague_json_is_free_and_skips_runner(monkeypatch):
  _auth(monkeypatch, credits=30)

  def _boom(**kw):
    raise AssertionError("runner must not run for vague questions")

  monkeypatch.setattr(main.runner, "run_async", _boom)
  charges = []
  monkeypatch.setattr(
    main, "_charge_and_log", lambda *a, **k: charges.append(1) or 20
  )
  frees = []
  monkeypatch.setattr(
    main, "_log_free_query", lambda *a: frees.append(a)
  )

  r = client.post("/chat", data={"message": "พิกัดศุลกากร"}, headers=AUTH)
  assert r.status_code == 200
  d = r.json()
  assert d["answer"] == main.CLARIFY_MD + main.FOOTER
  assert d["usage"]["free"] is True
  assert d["usage"]["est_cost_usd"] == 0.0
  assert d["usage"]["grounding_calls"] == 0
  assert d["credits_left"] == 30  # unchanged
  assert charges == []  # not charged
  assert len(frees) == 1 and frees[0][0] == "user1"


def test_vague_sse_yields_done_only(monkeypatch):
  _auth(monkeypatch, credits=30)
  monkeypatch.setattr(main, "_log_free_query", lambda *a: None)

  def _boom(**kw):
    raise AssertionError("runner must not run for vague questions")

  monkeypatch.setattr(main.runner, "run_async", _boom)

  r = client.post("/chat", data={"message": "hi"}, headers=SSE)
  assert r.status_code == 200
  events = _parse_sse(r.text)
  assert [e for e, _ in events] == ["done"]
  assert events[0][1]["usage"]["free"] is True
  assert events[0][1]["credits_left"] == 30


def test_vague_with_attachment_runs_runner(monkeypatch):
  _auth(monkeypatch, credits=30)
  monkeypatch.setattr(
    main.runner,
    "run_async",
    lambda **kw: _gen([_ev("ดูจากรูปแล้ว", partial=True), _ev("พิกัด 8518")]),
  )
  charges = []
  monkeypatch.setattr(
    main, "_charge_and_log", lambda *a, **k: charges.append(1) or 20
  )
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post(
    "/chat",
    data={"message": "พิกัดศุลกากร"},
    files={"file": ("pic.png", b"fake-image-bytes", "image/png")},
    headers=AUTH,
  )
  assert r.status_code == 200
  d = r.json()
  assert d["answer"] == "พิกัด 8518" + main.FOOTER  # normal path, charged
  assert d["usage"]["free"] is False
  assert len(charges) == 1


async def _gen(events):
  for e in events:
    yield e


def test_grounding_counts_unique_queries_not_events():
  acc = main._new_acc()
  main._accumulate_usage(_ev("a", partial=True, queries=["q1", "q2"]), acc)
  main._accumulate_usage(_ev("b", partial=True, queries=["q1", "q2"]), acc)
  main._accumulate_usage(_ev("c", queries=["q2", "q3"]), acc)
  usage = main._usage_dict(acc, 1.0)
  assert usage["grounding_calls"] == 3  # not 3 events, not 6 raw
  assert usage["est_cost_usd"] == round(3 / 1000 * main.GROUND_PER_1K, 4)
  assert usage["capped"] is False


def test_grounding_legacy_shape_counts_zero():
  acc = main._new_acc()
  ev = SimpleNamespace(
    content=SimpleNamespace(parts=[SimpleNamespace(text="x")]),
    partial=False,
    usage_metadata=None,
    grounding_metadata={},  # old fakes / shapeless metadata
  )
  main._accumulate_usage(ev, acc)
  assert main._usage_dict(acc, 1.0)["grounding_calls"] == 0


def test_breaker_trips_stops_early_and_uses_fallback(monkeypatch):
  _auth(monkeypatch, credits=30)
  consumed = []

  async def _spiral(**kw):
    for i in range(50):
      consumed.append(i)
      yield _ev("x", queries=[f"spiral-q{i}"])

  monkeypatch.setattr(main.runner, "run_async", _spiral)
  charges = []
  monkeypatch.setattr(
    main, "_charge_and_log", lambda *a, **k: charges.append(1) or 20
  )
  puts = []
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: puts.append(k))

  r = client.post("/chat", data={"message": REAL_Q}, headers=AUTH)
  assert r.status_code == 200
  d = r.json()
  assert len(consumed) == main.MAX_GROUNDING_QUERIES  # stopped, not 50
  assert d["usage"]["capped"] is True
  assert d["usage"]["grounding_calls"] == main.MAX_GROUNDING_QUERIES
  assert d["answer"] == main.CAPPED_MD + main.FOOTER  # thin answer -> fallback
  assert len(charges) == 1  # real spend still charged
  assert puts == []  # fallback never cached


def test_breaker_keeps_long_answer_and_caches(monkeypatch):
  _auth(monkeypatch, credits=30)

  async def _long(**kw):
    for i in range(main.MAX_GROUNDING_QUERIES):
      yield _ev("y" * 50, queries=[f"q{i}"])

  monkeypatch.setattr(main.runner, "run_async", _long)
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  puts = []
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: puts.append((k, a)))

  r = client.post("/chat", data={"message": REAL_Q}, headers=AUTH)
  assert r.status_code == 200
  d = r.json()
  assert d["usage"]["capped"] is True
  assert d["answer"] == "y" * 50 * main.MAX_GROUNDING_QUERIES + main.FOOTER
  assert len(puts) == 1  # full answer is cacheable


def test_normal_run_under_cap_not_capped(monkeypatch):
  _auth(monkeypatch, credits=30)

  async def _normal(**kw):
    yield _ev("half", partial=True, queries=["a", "b"])
    yield _ev("พิกัด 6109", queries=["a", "b", "c", "d", "e", "f", "g", "h"])

  monkeypatch.setattr(main.runner, "run_async", _normal)
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post("/chat", data={"message": REAL_Q}, headers=AUTH)
  assert r.status_code == 200
  d = r.json()
  assert d["usage"]["grounding_calls"] == 8  # probe-verified real shape
  assert d["usage"]["capped"] is False
  assert d["answer"] == "พิกัด 6109" + main.FOOTER


def test_agent_prompt_has_search_budget():
  from thai_customs_agent.agent import root_agent

  assert "ไม่เกิน 4 ครั้ง" in root_agent.instruction
