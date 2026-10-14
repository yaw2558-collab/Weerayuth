"""Tariff-book tool tests: exact/prefix lookup + keyword search.

Pure functions over tariff_data/tariff_slim.json (no model, no network).
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest thai_customs_agent/test_tariff_tools.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thai_customs_agent.tariff_tools import (
  extract_hs_codes,
  format_verify_box,
  lookup_tariff,
  retrieve_context,
  search_tariff,
)


def test_lookup_exact_coffee_wto_90():
  r = lookup_tariff("0901.21.20")
  assert r["match"] == "exact"
  line = r["lines"][0]
  assert line["wto"] == 90
  assert line["mfn"] is None  # no simple MFN column rate
  assert "Ground" in line["en"]
  assert any("อาหารและยา" in p for p in line["permits"])


def test_lookup_exact_smartphone_exempt():
  r = lookup_tariff("8517.13")
  assert r["match"] == "exact"
  line = r["lines"][0]
  assert line["hs"] == "8517.13.00"
  assert line["mfn_note"] == "exempt"
  assert line["fta"].get("ACN") == 0


def test_lookup_prefix_returns_family():
  r = lookup_tariff("6109.10")
  assert r["match"] == "prefix"
  assert r["count"] == 2
  assert {line["hs"] for line in r["lines"]} == {
    "6109.10.10",
    "6109.10.20",
  }
  assert all(line["mfn"] == 30 for line in r["lines"])


def test_lookup_too_short_and_unknown():
  assert "error" in lookup_tariff("12")
  assert "error" in lookup_tariff("abcd")
  r = lookup_tariff("9999")
  assert r["match"] == "none"


def test_search_thai_and_english():
  th = search_tariff("กาแฟ")
  assert th["count"] > 0
  assert any("0901" in line["hs"] for line in th["lines"])
  en = search_tariff("loudspeaker")
  assert en["count"] > 0
  assert any(line["hs"].startswith("8518") for line in en["lines"])


def test_search_short_and_limit():
  assert "error" in search_tariff("x")
  r = search_tariff("shoe", limit=3)
  assert len(r["lines"]) <= 3
  assert r["count"] >= len(r["lines"])


def test_retrieve_context_thai_keyword():
  ctx = retrieve_context("นำเข้ากาแฟคั่วบดจากจีน เสียอากรเท่าไหร่")
  assert "ฐานพิกัดทางการ" in ctx
  assert "0901.21.20" in ctx
  assert "90%" in ctx


def test_retrieve_context_explicit_code():
  ctx = retrieve_context("พิกัด 8517.13 เสียเท่าไหร่")
  assert "8517.13.00" in ctx
  assert "ยกเว้นอากร" in ctx


def test_retrieve_context_reaches_other_lines():
  # Sub-line descs say only "Other"/"For men..." — family pull must surface
  # 6404.11.90 and 6109.10.10 even though no keyword matches their text.
  shoes = retrieve_context("นำเข้ารองเท้าผ้าใบพื้นยางจากจีน ต้องเสียภาษีเท่าไหร่")
  assert "6404.11.90" in shoes
  assert "30%" in shoes
  shirt = retrieve_context("นำเข้าเสื้อยืดผ้าฝ้าย 100% แบบถัก จากจีน เสียอากรเท่าไหร่")
  assert "6109.10.10" in shirt
  assert "6109.10.20" in shirt


def test_retrieve_context_english_and_empty():
  ctx = retrieve_context("import duty for bluetooth speaker from china?")
  assert "ฐานพิกัดทางการ" in ctx
  assert "8518.21" in ctx
  assert retrieve_context("asdfgh qwerty") == ""


def test_verify_box_real_and_fake_codes():
  assert extract_hs_codes("พิกัด 0901.21.20 นะ [1]") == ["0901.21.20"]
  box = format_verify_box(["0901.21.20", "9999.99"])
  assert "0901.21.20" in box and "90%" in box
  assert "9999.99" in box and "ไม่พบในฐานพิกัดทางการ" in box
  assert format_verify_box([]) == ""
  assert format_verify_box(["0901.21"]) == ""  # real family, not a claim
  assert "ไม่พบ" in format_verify_box(["9999.99"])  # fake family still warns


def test_retrieve_context_fixture_pulls_machinery_families():
  # Regression (fixture จับยึดฐาน OSFP): industrial-goods questions used to
  # drown in EN-substring noise (ginseng, surfactants...) with zero Ch 84-85
  # lines, so the model invented 8486.90.90.
  q = (
    "อุปกรณ์จับยึดสำหรับติดตั้งฐาน 800G 2XFR4 OSFP ทำจากอะลูมิเนียม 95% "
    "ใช้สำหรับเครื่องจ่ายกาว dispensing machine ส่วนการผลิตเซมิคอนดักเตอร์ "
    "นำเข้าจากจีน เสียอากรเท่าไหร่"
  )
  ctx = retrieve_context(q)
  assert "8486.10.10" in ctx  # family pull: head of 8486
  assert "8486.90.49" in ctx  # family pull: tail of 8486
  assert "8479.90.90" in ctx  # family pull: tail of 8479 (parts answer)


def test_verify_box_corrects_nonexistent_subdivision():
  # 8486.90.90 looks plausible but does not exist in AHTN — the box must
  # correct with the real subdivision list, not just flag it.
  box = format_verify_box(["8486.90.90"])
  assert "ไม่มีรหัสนี้" in box
  assert "8486.90.11" in box
  assert "31 รหัส" in box
  assert "และอีก 21 รหัส" in box
