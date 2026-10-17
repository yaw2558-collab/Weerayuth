"""Static checks for the marketing site (served via GitHub Pages)."""
from pathlib import Path

SITE_INDEX = Path(__file__).resolve().parent / "index.html"


def test_contact_email_present():
  html = SITE_INDEX.read_text(encoding="utf-8")
  assert "mailto:yaw2558@gmail.com" in html


def test_lang_toggle_present():
  html = SITE_INDEX.read_text(encoding="utf-8")
  assert 'id="langbtn"' in html
  assert "data-i18n=" in html
  js = (SITE_INDEX.parent / "script.js").read_text(encoding="utf-8")
  assert "tc-lang" in js  # localStorage persistence key
  assert "Frequently asked questions" in js  # EN strings embedded


def test_chinese_present():
  js = (SITE_INDEX.parent / "script.js").read_text(encoding="utf-8")
  assert "常见问题" in js  # ZH strings embedded
  assert "nextLang" in js  # 3-way toggle


def test_homepage_links_blog():
  html = SITE_INDEX.read_text(encoding="utf-8")
  assert html.count('href="blog/"') >= 2  # top nav + footer
  js = (SITE_INDEX.parent / "script.js").read_text(encoding="utf-8")
  assert 'nav_blog: "Blog"' in js
  assert 'nav_blog: "博客"' in js


def test_blog_index_lists_articles():
  html = (SITE_INDEX.parent / "blog" / "index.html").read_text(
    encoding="utf-8"
  )
  assert "<h1>บทความ</h1>" in html
  assert "hs-code-lookup-guide.html" in html
  assert "gateway-1008099094873.asia-southeast1.run.app" in html  # CTA
  assert "mailto:yaw2558@gmail.com" in html
  assert "../styles.css" in html  # shared brand stylesheet


def test_article_seo_and_cta():
  html = (SITE_INDEX.parent / "blog" / "hs-code-lookup-guide.html").read_text(
    encoding="utf-8"
  )
  assert "<h1>" in html and "HS Code" in html
  assert '<meta name="description"' in html
  assert 'property="og:type" content="article"' in html
  assert "application/ld+json" in html  # Article schema
  assert "customs.go.th" in html  # official-source link
  assert "gateway-1008099094873.asia-southeast1.run.app" in html  # CTA
  assert "<details" in html  # FAQ accordions
  assert "../styles.css" in html
