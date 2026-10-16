"""Tariff-book tool tests: exact/prefix lookup + keyword search.

Pure functions over tariff_data/tariff_slim.json (no model, no network).
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest thai_customs_agent/test_tariff_tools.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thai_customs_agent.tariff_tools import (
  attachment_code_verdicts,
  extract_hs_codes,
  format_candidates,
  format_lookup_lines,
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


def test_format_candidates_fixture_lists_machinery_lines():
  q = (
    "อุปกรณ์จับยึดสำหรับติดตั้งฐาน 800G 2XFR4 OSFP ทำจากอะลูมิเนียม 95% "
    "ใช้สำหรับเครื่องจ่ายกาว dispensing machine ส่วนการผลิตเซมิคอนดักเตอร์ "
    "นำเข้าจากจีน เสียอากรเท่าไหร่"
  )
  cands = format_candidates(q)
  assert "8486.90.49" in cands
  assert "8479.90.90" in cands
  assert "MFN" in cands
  assert "ห้ามแต่งตัวเลข" not in cands  # no prompt instructions to users


def test_format_candidates_empty_when_no_match():
  assert format_candidates("asdfgh qwerty") == ""


def test_retrieve_context_file_text_keywords():
  # Attachment runs: the message is often vague ("พิกัดศุลกากร") with the
  # product words inside the file (fixture xlsx spirals).
  ctx = retrieve_context(
    "พิกัดศุลกากร",
    file_text="อุปกรณ์จับยึดสำหรับติดตั้งฐาน OSFP ส่วนการผลิตเซมิคอนดักเตอร์ เครื่องจ่ายกาว",
  )
  assert "8486.90.49" in ctx
  assert "8479.90.90" in ctx


def test_retrieve_context_file_text_ignores_digits_and_english():
  # Prices/years/dimensions and company names in files must not pollute.
  assert retrieve_context("พิกัดศุลกากร", file_text="ราคา 1234.56 บาท จำนวน 9999 ชิ้น ปี 2024") == ""
  assert retrieve_context("พิกัดศุลกากร", file_text="LOUDSPEAKER bluetooth ACME Corp Bangkok") == ""


def test_retrieve_context_lists_valid_subdivisions():
  # Regression: the model invented 8486.90.99 (".99 = Other" overgeneralized
  # from headings like 7326.90). Pre-answer valid lists constrain it.
  ctx = retrieve_context(
    "อุปกรณ์จับยึดสำหรับติดตั้งฐาน OSFP ส่วนการผลิตเซมิคอนดักเตอร์ เครื่องจ่ายกาว"
  )
  assert "รหัสย่อยที่มีจริง" in ctx
  assert "8486.90 มีรหัสย่อยจริง 31 รหัส" in ctx
  assert "8479.90 มีรหัสย่อยจริง 3 รหัส" in ctx
  line = next(
    ln for ln in ctx.splitlines() if ln.startswith("8486.90 มีรหัสย่อยจริง")
  )
  assert "8486.90.11" in line and "8486.90.49" in line
  assert "8486.90.99" not in line and "8486.90.90" not in line
  assert "2106.90 มีรหัสย่อยจริง" not in ctx  # substring noise stays out


def test_attachment_verdicts_reject_foreign_code():
  # Regression (prod 2026-10-16): supplier xlsx headlined Chinese HS
  # 8517795000 as the Thai answer. File HS claims get a deterministic
  # per-code verdict — fakes are banned pre-answer.
  out = attachment_code_verdicts("HS CODE 8517795000")
  assert "ตรวจรหัสในไฟล์แนบ" in out
  assert "8517.79.50" in out
  assert "ไม่มีรหัสนี้ในฐาน" in out
  assert "ห้ามอ้าง" in out
  assert "อ้างได้แค่ 6 หลัก" in out


def test_attachment_verdicts_confirm_real_code():
  out = attachment_code_verdicts("พิกัด 0901.21.20")
  assert "0901.21.20" in out
  assert "มีในฐานพิกัดไทย" in out
  assert "90%" in out


def test_attachment_verdicts_empty_without_codes():
  # Phone numbers and plain words are not HS claims (cue-gated runs only).
  assert attachment_code_verdicts("อุปกรณ์เซมิคอนดักเตอร์ โทร 0812345678") == ""
  assert attachment_code_verdicts("") == ""


def test_retrieve_context_fiber_module_pulls_8517():
  # Regression (prod 2026-10-16): the transceiver question pulled pure
  # noise (even shrimp) with zero Ch 85 lines, so the model clung to the
  # attachment's Chinese code.
  q = (
    "โมดูลรับส่งสัญญาณใยแก้วนำแสง ไม่รวมตัวเรือน "
    "OPTICAL TRANSCEIVER MODULE นำเข้าจากจีน เสียอากรเท่าไหร่"
  )
  ctx = retrieve_context(q)
  assert "8517" in ctx
  assert "8517.79 มีรหัสย่อยจริง 9 รหัส" in ctx


def test_format_lookup_lines_skips_fakes_and_families():
  out = format_lookup_lines(["8486.90.99", "0901.21", "0901.21.20", "7326.90.99"])
  assert "8486.90.99" not in out
  assert "0901.21.20" in out and "90%" in out
  assert "7326.90.99" in out and "MFN 10%" in out
  assert format_lookup_lines(["9999.99.99"]) == ""
  assert format_lookup_lines([]) == ""
