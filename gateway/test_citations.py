"""Citation tests: verifiable source links, [n] strip, disclaimer backstop.

Seams faked at the boundary: _verify, _get_or_create_user, _check_rate,
runner.run_async, _cache_get/_cache_put, _charge_and_log.
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_citations.py
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}
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


def _chunk(uri, title):
  return SimpleNamespace(web=SimpleNamespace(uri=uri, title=title))


def _ev(text, partial=False, chunks=None, queries=None):
  gm = None
  if chunks is not None or queries is not None:
    gm = SimpleNamespace(
      grounding_chunks=list(chunks or []),
      web_search_queries=list(queries or []),
    )
  return SimpleNamespace(
    content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
    partial=partial,
    usage_metadata=None,
    grounding_metadata=gm,
  )


def test_sources_collected_deduped_and_capped():
  acc = main._new_acc()
  main._accumulate_usage(
    _ev("a", chunks=[_chunk("https://x/1", "One")], queries=["q1"]), acc
  )
  main._accumulate_usage(
    _ev(
      "b",
      chunks=[_chunk("https://x/1", "One dup"), _chunk("https://x/2", "Two")],
      queries=["q1", "q2"],
    ),
    acc,
  )
  assert acc["sources"] == [
    ("One", "https://x/1"),
    ("Two", "https://x/2"),
  ]
  assert len(acc["seen"]) == 2


def test_sources_collect_retrieved_context_shape():
  acc = main._new_acc()
  ev = SimpleNamespace(
    content=SimpleNamespace(parts=[SimpleNamespace(text="x")]),
    partial=False,
    usage_metadata=None,
    grounding_metadata=SimpleNamespace(
      web_search_queries=[],
      grounding_chunks=[
        SimpleNamespace(
          web=None,
          retrieved_context=SimpleNamespace(
            uri="https://www.customs.go.th/p", title="Tariff page"
          ),
        )
      ],
    ),
  )
  main._accumulate_usage(ev, acc)
  assert acc["sources"] == [("Tariff page", "https://www.customs.go.th/p")]


def test_finalize_strips_markers_appends_links_and_disclaimer():
  acc = main._new_acc()
  acc["sources"] = [("Customs", "https://www.customs.go.th/x")]
  out = main._finalize_answer("พิกัด 8518[12] ตามนี้[3] และ[2, 3, 4]", acc)
  assert "[12]" not in out and "[3]" not in out and "[2, 3, 4]" not in out
  assert "ลิงก์อ้างอิงที่ตรวจสอบได้" in out
  assert "[Customs](https://www.customs.go.th/x)" in out
  assert "Advance Ruling" in out  # backstop added


def test_finalize_keeps_existing_disclaimer():
  acc = main._new_acc()
  out = main._finalize_answer("ตอบแล้ว (Advance Ruling) ครับ", acc)
  assert out.count("Advance Ruling") == 1  # not duplicated
  assert "ลิงก์อ้างอิง" not in out  # no sources, no section


def test_chat_json_answer_finalized_end_to_end(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main.runner,
    "run_async",
    _fake_run([
      _ev(
        "พิกัด 8518[7]",
        chunks=[_chunk("https://www.customs.go.th/t", "Tariff")],
        queries=["q"],
      )
    ]),
  )
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  puts = []
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: puts.append(a))

  r = client.post("/chat", data={"message": REAL_Q}, headers=AUTH)
  assert r.status_code == 200
  d = r.json()
  assert "[7]" not in d["answer"]
  assert "(https://www.customs.go.th/t)" in d["answer"]
  assert "Advance Ruling" in d["answer"]
  assert puts and "(https://www.customs.go.th/t)" in puts[0]  # cached final


def test_chat_injects_tariff_context_to_runner(monkeypatch):
  _auth(monkeypatch)
  seen = {}

  async def _capture(**kw):
    seen["msg"] = kw["new_message"]
    yield _ev("พิกัด 8518", queries=["q"])

  monkeypatch.setattr(main.runner, "run_async", _capture)
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post("/chat", data={"message": REAL_Q}, headers=AUTH)
  assert r.status_code == 200
  text = seen["msg"].parts[0].text
  assert "ฐานพิกัดทางการ" in text
  assert "8518.21" in text
  assert REAL_Q in text  # original question preserved


def test_chat_appends_verify_box_for_answer_codes(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main.runner, "run_async", _fake_run([_ev("พิกัด 0901.21.20 ครับ", queries=["q"])])
  )
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post(
    "/chat", data={"message": "นำเข้ากาแฟคั่วบดจากจีน เสียอากรเท่าไหร่"}, headers=AUTH
  )
  assert r.status_code == 200
  d = r.json()
  assert "ตรวจสอบอัตราจากฐานพิกัดทางการ" in d["answer"]
  assert "90%" in d["answer"]


def _fake_run(events):
  async def _gen(**kw):
    for e in events:
      yield e

  return _gen
