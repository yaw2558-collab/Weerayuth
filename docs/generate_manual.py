"""Build customer manuals (Thai + English PDFs) from docs/manual-{th,en}.md.

Run from thai-customs/: ..\\.venv\\Scripts\\python docs/generate_manual.py
Requires: fpdf2, uharfbuzz (Thai shaping), docs/fonts/Sarabun-*.ttf
"""

import re
from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).parent
BRAND = (12, 74, 66)
INK = (31, 41, 51)
MUTED = (107, 114, 128)


def zwsp(text: str) -> str:
  """Insert zero-width spaces for Thai line-breaking (keeps URLs intact)."""
  parts = re.split(r"(https?://\S+)", text)
  for i in range(0, len(parts), 2):
    parts[i] = "\u200b".join(list(parts[i]))
  return "".join(parts)


class Manual(FPDF):
  title_text = ""

  def footer(self):
    self.set_y(-15)
    self.set_font("Sarabun", "", 9)
    self.set_text_color(*MUTED)
    self.cell(0, 10, f"{self.title_text}  |  {self.page_no()}/{{nb}}", align="C")


def build(md_path: Path, pdf_path: Path) -> int:
  lines = md_path.read_text(encoding="utf-8").splitlines()
  pdf = Manual()
  pdf.set_auto_page_break(True, margin=20)
  pdf.set_text_shaping(True)
  pdf.add_font("Sarabun", "", HERE / "fonts" / "Sarabun-Regular.ttf")
  pdf.add_font("Sarabun", "B", HERE / "fonts" / "Sarabun-Bold.ttf")
  pdf.alias_nb_pages("{nb}")
  pdf.add_page()
  pdf.set_text_color(*INK)

  first = True
  for raw in lines:
    line = raw.rstrip()
    if not line.strip():
      pdf.ln(3)
      continue
    pdf.set_x(pdf.l_margin)
    if line.startswith("# ") and first:
      first = False
      pdf.title_text = line[2:].strip()
      pdf.set_font("Sarabun", "B", 22)
      pdf.set_text_color(*BRAND)
      pdf.multi_cell(0, 10, zwsp(line[2:].strip()))
      pdf.set_draw_color(*BRAND)
      pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.w - pdf.r_margin, pdf.get_y() + 2)
      pdf.ln(6)
      pdf.set_text_color(*INK)
      continue
    first = False
    if line.startswith("## "):
      pdf.ln(2)
      pdf.set_font("Sarabun", "B", 15)
      pdf.set_text_color(*BRAND)
      pdf.multi_cell(0, 8, zwsp(line[3:].strip()))
      pdf.set_text_color(*INK)
      pdf.ln(1)
      continue
    m = re.match(r"^(\d+)\.\s+(.*)", line)
    bullet = re.match(r"^[-*]\s+(.*)", line)
    pdf.set_font("Sarabun", "", 12)
    if m:
      pdf.multi_cell(0, 7, f"  {m.group(1)}.  {zwsp(m.group(2))}")
    elif bullet:
      pdf.multi_cell(0, 7, f"  \u2022  {zwsp(bullet.group(1))}")
    else:
      pdf.multi_cell(0, 7, zwsp(line))
  pdf.output(pdf_path)
  return pdf.page_no()


if __name__ == "__main__":
  for lang in ("th", "en"):
    n = build(HERE / f"manual-{lang}.md", HERE / f"manual-{lang}.pdf")
    print(f"manual-{lang}.pdf: {n} pages")
