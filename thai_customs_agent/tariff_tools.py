"""Local tariff-book tools: exact rates from the official ITD master files.

Free (no model/search cost) and deterministic. The agent must consult these
before quoting any duty rate, so numbers come from the tariff book — not blogs.
Data: tariff_data/tariff_slim.json (see SOURCE.md for provenance).
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).parent / "tariff_data" / "tariff_slim.json"
_MAX_HITS = 20

_HS_RE = re.compile(r"\b(\d{4})\s?\.?\s?(\d{2})(?:\s?\.?\s?(\d{2}))?\b")
_HS_FINDER = re.compile(r"\b\d{4}\.\d{2}(?:\.\d{2})?\b")

# Thai has no word boundaries, so scan messages for these product words.
_TH_KEYWORDS = (
  "ลำโพง", "หูฟัง", "ไมโครโฟน", "กาแฟ", "โกโก้", "น้ำตาล", "ข้าว",
  "รองเท้า", "ผ้าใบ", "เสื้อยืด", "เสื้อ", "กางเกงยีนส์", "กางเกง", "ยีนส์",
  "กระเป๋า", "นาฬิกา", "แว่นตา", "แว่น", "หมวก", "ถุงเท้า", "ชุดชั้นใน",
  "สมาร์ทโฟน", "โทรศัพท์", "มือถือ", "แท็บเล็ต", "โน้ตบุ๊ก", "คอมพิวเตอร์",
  "เมาส์", "คีย์บอร์ด", "โทรทัศน์", "ทีวี", "ตู้เย็น", "เครื่องปรับอากาศ",
  "แอร์", "พัดลม", "หม้อหุงข้าว", "ไมโครเวฟ", "เครื่องซักผ้า", "ของเล่น",
  "ตุ๊กตา", "จักรยาน", "มอเตอร์ไซค์", "รถยนต์", "ยางรถ", "แบตเตอรี่",
  "ถ่าน", "หลอดไฟ", "โคมไฟ", "เครื่องสำอาง", "ลิปสติก", "ครีม", "แชมพู",
  "สบู่", "ยาสีฟัน", "วิตามิน", "อาหารเสริม", "ช็อกโกแลต", "ขนม", "บะหมี่",
  "น้ำมัน", "ปุ๋ย", "เมล็ด", "ผลไม้", "ทุเรียน", "หน้ากาก", "เครื่องมือ",
  "สว่าน", "กุญแจ", "กระดาษ", "ปากกา", "เฟอร์นิเจอร์", "เก้าอี้", "โต๊ะ",
  "เตียง", "พรม", "ม่าน", "มีด", "ชา", "ยา", "นม",
  # Process / state / material words: sub-line descriptions often name only
  # these (e.g. "บด" for 0901.21.20), with the product word on the parent line.
  # (ผ้า/ยาง/ไม้/แก้ว dropped: too generic, only add noise.)
  "คั่ว", "บด", "อบ", "ทอด", "แห้ง", "สด", "แช่แข็ง", "แช่เย็น", "กระป๋อง",
  "ผง", "เม็ด", "แผ่น", "ม้วน", "ทอ", "ถัก", "เย็บ", "สำเร็จรูป", "ชิ้นส่วน",
  "อะไหล่", "มือสอง", "พลาสติก", "เหล็ก", "อลูมิเนียม", "ทองแดง",
  "เซรามิก", "หนัง",
  # Machinery / industrial goods (Ch 84-85 recall): without these, parts
  # questions drown in EN-substring noise and the model invents codes.
  # Order matters: specific first, generic "เครื่อง" last (family quota).
  "เซมิคอนดักเตอร์", "เครื่อง",
)

_EN_STOP = frozenset(
  "what how much many why when where which that this with from your you "
  "rate rates duty duties code codes import imports importation customs "
  "tariff tax taxes cost costs price prices shipping thailand thai china "
  "chinese please know want form for the and are does did can could would "
  "should rcep acfta fta".split()
)

# Product keyword -> HS headings (first 4 raw digits). Sub-line descriptions
# often say only "Other" / "For men..." with the product word on the missing
# parent line, so keyword substring alone can never reach them (e.g. shoes).
# Pulling the whole family fixes recall; the model picks the right line.
_HEADING_MAP = {
  "รองเท้า": ("6404", "6403", "6402", "6401"),
  "เสื้อยืด": ("6109",), "เสื้อ": ("6109", "6110", "6205", "6206"),
  "กางเกง": ("6104", "6203", "6204"), "ยีนส์": ("6104", "6203"),
  "ถุงเท้า": ("6115",), "ชุดชั้นใน": ("6107", "6207"),
  "กระเป๋า": ("4202",),
  "นาฬิกา": ("9101", "9102"),
  "แว่นตา": ("9004",), "แว่น": ("9004",),
  "หมวก": ("6504", "6505", "6506"),
  "กาแฟ": ("0901", "2101"), "ชา": ("0902", "2101"),
  "ลำโพง": ("8518",), "หูฟัง": ("8518",), "ไมโครโฟน": ("8518",),
  "สมาร์ทโฟน": ("8517",), "โทรศัพท์": ("8517",), "มือถือ": ("8517",),
  "แท็บเล็ต": ("8471",), "โน้ตบุ๊ก": ("8471",), "คอมพิวเตอร์": ("8471",),
  "เมาส์": ("8473",), "คีย์บอร์ด": ("8473",),
  "โทรทัศน์": ("8528",), "ทีวี": ("8528",),
  "ตู้เย็น": ("8418",), "เครื่องปรับอากาศ": ("8415",), "แอร์": ("8415",),
  "พัดลม": ("8414",), "หม้อหุงข้าว": ("8516",), "ไมโครเวฟ": ("8516",),
  "เครื่องซักผ้า": ("8450",),
  "ของเล่น": ("9503",), "ตุ๊กตา": ("9503",),
  "จักรยาน": ("8712",), "รถยนต์": ("8703", "8704"),
  "มอเตอร์ไซค์": ("8711",),
  "แบตเตอรี่": ("8506", "8507"), "ถ่าน": ("8506", "8507"),
  "หลอดไฟ": ("8539",), "โคมไฟ": ("9405",),
  "เครื่องสำอาง": ("3304",), "ลิปสติก": ("3304",), "ครีม": ("3304",),
  "แชมพู": ("3401",), "สบู่": ("3401",),
  "วิตามิน": ("2106",), "อาหารเสริม": ("2106",),
  "ช็อกโกแลต": ("1806",), "ขนม": ("1704", "1905"),
  "นม": ("0401", "0402"), "ยา": ("3004",), "หน้ากาก": ("6307",),
  "เฟอร์นิเจอร์": ("9401", "9403"), "เก้าอี้": ("9401",),
  "โต๊ะ": ("9403",), "เตียง": ("9403",), "พรม": ("5702", "5703"),
  "ม่าน": ("6303",), "มีด": ("8211",),
  "สว่าน": ("8467",), "เครื่องมือ": ("8205", "8467"), "กุญแจ": ("8301",),
  "ปากกา": ("9608",), "กระดาษ": ("4802",),
  "ข้าว": ("1006",), "น้ำตาล": ("1701",), "ปุ๋ย": ("3105",),
  "ผลไม้": ("0810",), "ทุเรียน": ("0810",),
  "ผ้าใบ": ("5901",),
  "เซมิคอนดักเตอร์": ("8486",),
  "เครื่อง": ("8479",),
}


@lru_cache(maxsize=1)
def _load() -> dict:
  data = json.loads(_DATA.read_text(encoding="utf-8"))
  by_raw = {line["raw"]: line for line in data["lines"]}
  by_head: dict[str, list] = {}
  for line in data["lines"]:
    by_head.setdefault(line["raw"][:4], []).append(line)
  return {
    "meta": data["meta"],
    "lines": data["lines"],
    "by_raw": by_raw,
    "by_head": by_head,
  }


def _slim(line: dict) -> dict:
  return {
    "hs": line["c"],
    "th": line["th"],
    "en": line["en"],
    "mfn": line["mfn"],
    "mfn_note": line["mfn_text"],
    "wto": line["wto"],
    "fta": line["fta"],
    "section12": line["sec12"],
    "permits": line["permit"],
  }


def lookup_tariff(hs_code: str) -> dict:
  """ค้นอัตราอากรที่แน่นอนของพิกัด HS/AHTN จากฐานพิกัดทางการของกรมศุลกากร
  (ITD, HS2022). Look up exact duty rates for an HS/AHTN code.

  ใช้ทุกครั้งก่อนตอบอัตราอากร. `mfn` = อัตราทั่วไปที่ใช้จริง (headline),
  `wto` = อัตราผูกพัน WTO (อ้างอิง), `fta` = อัตรา FTA รายความตกลง
  (จีน: ACN=ACFTA/Form E, R1C/R2C/R3C=RCEP — ต้องมี Form ประกอบ),
  `section12` = อัตราลดตามมาตรา 12 (ถ้ามี), `permits` = หน่วยงานคุมนำเข้า.
  ถ้าไม่มีอัตราในฐานข้อมูล ให้บอกว่าไม่พบ ห้ามแต่งตัวเลข.
  """
  raw = "".join(ch for ch in (hs_code or "") if ch.isdigit())
  if len(raw) < 4:
    return {"error": "need at least 4 digits, e.g. '8518' or '8518.21'"}
  t = _load()
  if len(raw) >= 8 and raw[:8] in t["by_raw"]:
    return {"match": "exact", "lines": [_slim(t["by_raw"][raw[:8]])]}
  hits = [line for line in t["lines"] if line["raw"].startswith(raw)]
  if not hits:
    return {"match": "none", "hint": "try search_tariff with a product word"}
  if len(hits) == 1:
    return {"match": "exact", "lines": [_slim(hits[0])]}
  return {
    "match": "prefix",
    "count": len(hits),
    "lines": [_slim(line) for line in hits[:_MAX_HITS]],
  }


def search_tariff(keyword: str, limit: int = 10) -> dict:
  """ค้นหาพิกัดจากคำสำคัญ (ไทย/อังกฤษ) ในฐานพิกัดทางการ.
  Find tariff lines by keyword, e.g. 'loudspeaker', 'กาแฟ', 'รองเท้า'.

  ใช้เมื่อยังไม่รู้พิกัดของสินค้า. คืนรายการพิกัดพร้อมอัตรา MFN/WTO/FTA.
  """
  kw = (keyword or "").strip().lower()
  if len(kw) < 2:
    return {"error": "keyword too short"}
  try:
    n = max(1, min(int(limit), _MAX_HITS))
  except (TypeError, ValueError):
    n = 10
  t = _load()
  hits = [
    line
    for line in t["lines"]
    if kw in line["th"].lower() or kw in line["en"].lower()
  ]
  return {
    "count": len(hits),
    "lines": [_slim(line) for line in hits[:n]],
  }


def _fmt_rates(line: dict) -> str:
  mfn = line["mfn"]
  if line["mfn_note"] == "exempt":
    mfn_s = "ยกเว้นอากร"
  elif mfn is None:
    mfn_s = line["mfn_note"] or "ไม่ระบุ"
  else:
    mfn_s = f"{mfn}%"
  wto = line["wto"]
  wto_s = f"{wto}%" if wto is not None else "-"
  fta = line["fta"] or {}
  parts = []
  if "ACN" in fta:
    parts.append(f"ACFTA(Form E) {fta['ACN']}%")
  rcep = [v for k, v in fta.items() if k.startswith("R") and len(k) == 3]
  if rcep:
    parts.append(
      f"RCEP {rcep[0]}%"
      if len(set(rcep)) == 1
      else f"RCEP {min(rcep)}–{max(rcep)}%"
    )
  fta_s = ", ".join(parts) if parts else "ไม่พบในฐาน"
  return f"MFN {mfn_s} | WTO {wto_s} | FTA(จีน) {fta_s}"


def _fmt_line(line: dict) -> str:
  desc = line["th"] or line["en"]
  permits = ", ".join(line["permits"]) if line["permits"] else "-"
  return (
    f"{line['hs']} | {desc} | {_fmt_rates(line)} | ใบอนุญาต: {permits}"
  )


def _collect(message: str, max_lines: int) -> list[dict]:
  """Collect up to max_lines slim tariff lines for a message (deterministic).

  Fill order: explicit HS digits, then family pulls (first 3 + last line per
  mapped heading — the ".90 Other" catch-all is usually last and usually the
  answer), then keyword substring round-robin for the remaining quota.
  """
  def _specific_first(lines):
    # Short descriptions matching the keyword are usually the most specific
    # (e.g. "บด" beats "เนื้อที่บดแยกเอากระดูกออก..."). HS-digit buckets keep
    # code order (exact match already first).
    return sorted(lines, key=lambda line: len(line["th"] + line["en"]))

  found: dict[str, dict] = {}

  def _take(line):
    if len(found) < max_lines:
      found.setdefault(line["hs"], line)

  # Phase 1: explicit HS digits, exact first.
  for m in _HS_RE.finditer(message or ""):
    raw = m.group(1) + m.group(2) + (m.group(3) or "")
    for line in lookup_tariff(raw).get("lines", [])[:4]:
      _take(line)
  # Phase 2: family pulls for mapped keywords (own quota so substring
  # buckets cannot crowd out the right chapter).
  fam_quota = min(8, max_lines)
  for kw in _TH_KEYWORDS:
    if kw not in (message or "") or kw not in _HEADING_MAP:
      continue
    for head in _HEADING_MAP[kw]:
      grouped = _load()["by_head"].get(head, [])
      picks = (grouped[:3] + grouped[-1:]) if len(grouped) > 3 else grouped
      for line in picks:
        if len(found) >= fam_quota:
          break
        _take(_slim(line))
  # Phase 3: keyword substring round-robin for the remaining quota.
  buckets: list[list] = []
  for kw in _TH_KEYWORDS:
    if kw in (message or ""):
      buckets.append(_specific_first(search_tariff(kw, limit=8).get("lines", [])))
  for tok in re.findall(r"[A-Za-z]{3,}", message or ""):
    if tok.lower() in _EN_STOP:
      continue
    buckets.append(_specific_first(search_tariff(tok, limit=4).get("lines", [])))
  idx = 0
  while len(found) < max_lines:
    progressed = False
    for b in buckets:
      if idx < len(b):
        progressed = True
        _take(b[idx])
        if len(found) >= max_lines:
          break
    if not progressed:
      break
    idx += 1
  return list(found.values())[:max_lines]


def retrieve_context(message: str, max_lines: int = 12) -> str:
  """ดึงพิกัดที่เกี่ยวข้องจากคำถาม เพื่อแนบเป็น context ให้โมเดล.

  Returns a formatted block ("" when nothing matches). Deterministic, $0.
  """
  lines = _collect(message, max_lines)
  if not lines:
    return ""
  body = "\n".join(_fmt_line(line) for line in lines)
  return (
    "[ฐานพิกัดทางการ (ITD HS2022) — ใช้ตัวเลขนี้เป็นหลัก ห้ามแต่งตัวเลข]\n"
    + body
  )


def format_candidates(message: str, max_lines: int = 8) -> str:
  """User-facing ITD candidate lines for the breaker fallback ($0, no model).

  "" when nothing matches (caller then uses the generic fallback text).
  """
  lines = _collect(message, max_lines)
  if not lines:
    return ""
  return "\n".join(_fmt_line(line) for line in lines)


def extract_hs_codes(text: str, limit: int = 5) -> list[str]:
  seen: dict[str, None] = {}
  for m in _HS_FINDER.finditer(text or ""):
    if len(seen) >= limit:
      break
    seen.setdefault(m.group(0))
  return list(seen)


_CORRECTION_SHOW = 10  # real subdivisions listed when an answer cites a code that does not exist


def _compact_rate(line: dict) -> str:
  if line["mfn_note"] == "exempt":
    return "ยกเว้นอากร"
  mfn = line["mfn"]
  if mfn is not None:
    return f"{mfn}%"
  return line["mfn_note"] or "ไม่ระบุ"


def _correction_block(code: str, digits: str) -> list[str]:
  """Correction for an 8-digit code missing from the book: list the real
  subdivisions under its 6-digit family so the user can pick correctly."""
  fam = lookup_tariff(digits[:6])
  lines = fam.get("lines", [])
  if fam.get("match") == "none" or not lines:
    return [f"- {code}: ไม่พบในฐานพิกัดทางการ (ITD) — โปรดตรวจสอบ"]
  total = fam.get("count", len(lines))
  head = f"{digits[:4]}.{digits[4:6]}"
  rows = [
    f"- {code}: ไม่มีรหัสนี้ในฐานพิกัดทางการ (ITD HS2022)",
    f"  รหัสที่มีจริงภายใต้ {head} ({total} รหัส):",
  ]
  for ln in lines[:_CORRECTION_SHOW]:
    desc = ln["th"] or ln["en"]
    rows.append(f"  - {ln['hs']} | {desc} | MFN {_compact_rate(ln)}")
  if total > _CORRECTION_SHOW:
    rows.append(f"  - ... และอีก {total - _CORRECTION_SHOW} รหัส")
  return rows


def format_verify_box(codes: list[str]) -> str:
  """กล่องตรวจเลขท้าย: เทียบพิกัดในคำตอบกับฐานทางการ + ดักรหัสแต่ง."""
  rows = []
  for code in codes[:5]:
    digits = "".join(ch for ch in code if ch.isdigit())
    r = lookup_tariff(code)
    if r.get("match") == "none" or "error" in r:
      if len(digits) >= 8:
        rows.extend(_correction_block(code, digits))
      else:
        rows.append(f"- {code}: ไม่พบในฐานพิกัดทางการ (ITD) — โปรดตรวจสอบ")
      continue
    if len(digits) < 8:
      continue  # real 6-digit family mention, not a rate claim — skip noise
    line = r["lines"][0]
    rows.append(f"- {_fmt_line(line)}")
  if not rows:
    return ""
  return "**ตรวจสอบอัตราจากฐานพิกัดทางการ (ITD):**\n" + "\n".join(rows)
