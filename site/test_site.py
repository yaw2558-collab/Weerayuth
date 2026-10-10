"""Static checks for the marketing site (served via GitHub Pages)."""
from pathlib import Path

SITE_INDEX = Path(__file__).resolve().parent / "index.html"


def test_contact_email_present():
  html = SITE_INDEX.read_text(encoding="utf-8")
  assert "mailto:yaw2558@gmail.com" in html
