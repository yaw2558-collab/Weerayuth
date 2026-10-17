"""Answer-language tests: AI answers follow the UI language (TH/EN/ZH).

The frontend sends its tc-lang with every /chat call. Thai stays the
default; EN/ZH get a per-message directive (codes/rates/ITD text copied
verbatim, never translated) plus localized deterministic templates
(clarify, breaker, verify box, disclaimer, footer). Cache keys are
scoped by language so a cached Thai answer is never served to EN/ZH.

Seams faked at the boundary: _verify, _get_or_create_user, _check_rate,
runner.run_async, enrich_runner.run_async, _cache_get/_cache_put,
_charge_and_log, _log_free_query.
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_lang.py
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


def _ev(text, partial=False, usage=None):
  return SimpleNamespace(
    content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
    partial=partial,
    usage_metadata=usage,
    grounding_metadata=None,
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


def test_normalize_lang_table():
  assert main._normalize_lang("th") == "th"
  assert main._normalize_lang("en") == "en"
  assert main._normalize_lang("zh") == "zh"
  assert main._normalize_lang("EN") == "en"  # case-insensitive
  assert main._normalize_lang("") == "th"
  assert main._normalize_lang(None) == "th"
  assert main._normalize_lang("xx") == "th"  # unknown -> Thai default
  assert main._normalize_lang("en-US") == "th"  # only bare codes accepted


def test_cache_key_scoped_by_lang():
  n = main._normalize_question("ถาม HS")
  k_th = main._cache_key(n, "th")
  assert k_th == main._cache_key(n)  # default stays Thai
  assert main._cache_key(n, "en") != k_th
  assert main._cache_key(n, "zh") != k_th
  assert main._cache_key(n, "en") != main._cache_key(n, "zh")
  assert len(k_th) == 64


def test_lang_directives_carry_canonical_refusal():
  # Each directive must use a refusal sentence the enrich pass detects,
  # else EN/ZH answers with missing rates never get enriched.
  for lang in ("en", "zh"):
    d = main._LANG_DIRECTIVE[lang]
    assert any(m in d for m in main._REFUSAL_MARKERS), lang
  assert "th" not in main._LANG_DIRECTIVE  # Thai is the model default


def test_templates_cover_all_langs():
  for table in (
    main.CLARIFY,
    main.CAPPED,
    main.DISCLAIMER,
    main.FOOTER,
    main.SOURCES_HDR,
    main.STAGE,
    main.BREAKER_HDR,
  ):
    assert set(table) == {"th", "en", "zh"}
    assert all(isinstance(v, str) and v.strip() for v in table.values())
  for lang in ("th", "en", "zh"):
    # Backstop check is the literal "Advance Ruling" — every disclaimer
    # must carry it or finalize() would double-append.
    assert "Advance Ruling" in main.DISCLAIMER[lang]
    assert "mailto:yaw2558@gmail.com" in main.FOOTER[lang]
    assert "lin.ee/Z55Jn7C" in main.FOOTER[lang]


def test_finalize_answer_uses_lang():
  acc = main._new_acc()
  acc["sources"] = [("Customs", "https://www.customs.go.th/x")]
  out = main._finalize_answer("HS 8518 answer", acc, "en")
  assert "Verifiable reference links" in out
  assert "preliminary reference" in out
  assert "ลิงก์อ้างอิง" not in out
  out_zh = main._finalize_answer("HS 8518 答案", main._new_acc(), "zh")
  assert "可验证的参考链接" not in out_zh  # no sources, no section
  assert "初步参考" in out_zh


def test_breaker_fallback_uses_lang():
  generic = main._breaker_fallback("Form E ใช้ยังไง", "en")
  assert main.CAPPED["en"] in generic
  assert main.DISCLAIMER["en"] in generic
  assert "ค้นข้อมูลหลายรอบ" not in generic
  cands = main._breaker_fallback(REAL_Q, "zh")
  assert "8518" in cands  # deterministic ITD candidates, $0
  assert "ITD HS2022" in cands
  assert main.DISCLAIMER["zh"] in cands


def test_verify_box_uses_lang():
  from thai_customs_agent.tariff_tools import format_verify_box

  real = format_verify_box(["9403.20.90"], "en")
  assert real.startswith("**Verify rates against")
  assert "9403.20.90" in real
  assert "อื่น ๆ" in real  # official ITD description stays Thai
  fake = format_verify_box(["9031.49.00"], "en")
  assert "not in the official tariff base" in fake
  assert "real subdivisions under 9031.49" in fake
  fake_zh = format_verify_box(["9031.49.00"], "zh")
  assert "官方税则库" in fake_zh
  assert "子目" in fake_zh
  th = format_verify_box(["9403.20.90"])
  assert th.startswith("**ตรวจสอบอัตรา")


def test_chat_sends_lang_directive_to_model(monkeypatch):
  _auth(monkeypatch)
  seen = {}

  async def _capture(**kw):
    seen.update(kw)
    yield _ev("HS 8518", usage=_usage())

  monkeypatch.setattr(main.runner, "run_async", _capture)
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post(
    "/chat", data={"message": REAL_Q, "lang": "en"}, headers=AUTH
  )
  assert r.status_code == 200
  sent = seen["new_message"].parts[-1].text
  assert "[Answer language: English" in sent
  assert r.json()["answer"].endswith(main.FOOTER["en"])

  r = client.post("/chat", data={"message": REAL_Q}, headers=AUTH)
  assert r.status_code == 200
  sent = seen["new_message"].parts[-1].text
  assert "[Answer language:" not in sent  # Thai default: no directive
  assert "[回答语言" not in sent
  assert r.json()["answer"].endswith(main.FOOTER["th"])


def test_chat_vague_en_is_free_template(monkeypatch):
  _auth(monkeypatch)

  def _boom(**kw):
    raise AssertionError("runner must not run for vague questions")

  monkeypatch.setattr(main.runner, "run_async", _boom)
  charges = []
  monkeypatch.setattr(
    main, "_charge_and_log", lambda *a, **k: charges.append(1) or 20
  )
  monkeypatch.setattr(main, "_log_free_query", lambda *a: None)

  r = client.post(
    "/chat", data={"message": "hs code", "lang": "en"}, headers=AUTH
  )
  assert r.status_code == 200
  d = r.json()
  assert d["answer"] == main.CLARIFY["en"] + main.FOOTER["en"]
  assert d["usage"]["free"] is True
  assert charges == []


def test_chat_caches_per_lang(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main.runner, "run_async", _fake_run([_ev("HS 8518", usage=_usage())])
  )
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  puts = []
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: puts.append(k))

  for lang in ("th", "en"):
    r = client.post(
      "/chat", data={"message": REAL_Q, "lang": lang}, headers=AUTH
    )
    assert r.status_code == 200
  assert len(puts) == 2
  assert puts[0] != puts[1]  # same question, separate cache entries


def test_enrich_prompt_keeps_answer_language(monkeypatch):
  _auth(monkeypatch)
  monkeypatch.setattr(
    main.runner,
    "run_async",
    _fake_run([
      _ev(
        "HS 7326.90.99, see the verification box below",
        usage=_usage(),
      )
    ]),
  )
  seen = {}

  async def _enrich(**kw):
    seen.update(kw)
    yield _ev("x" * 120, usage=_usage())

  monkeypatch.setattr(main.enrich_runner, "run_async", _enrich)
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: 20)
  monkeypatch.setattr(main, "_cache_put", lambda k, a, u: None)

  r = client.post(
    "/chat", data={"message": REAL_Q, "lang": "en"}, headers=AUTH
  )
  assert r.status_code == 200
  prompt = seen["new_message"].parts[0].text
  assert "Rewrite in English" in prompt
  assert "7326.90.99" in prompt  # real code still feeds enrichment
