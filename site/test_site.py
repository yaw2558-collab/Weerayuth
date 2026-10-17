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


ARTICLES = [
  "hs-code-lookup-guide.html",
  "import-duty-guide.html",
  "form-e-guide.html",
  "rcep-vs-acfta.html",
  "advance-ruling-guide.html",
]


def test_blog_index_lists_articles():
  html = (SITE_INDEX.parent / "blog" / "index.html").read_text(
    encoding="utf-8"
  )
  assert "<h1>บทความ</h1>" in html
  for slug in ARTICLES:
    assert slug in html
  assert "gateway-1008099094873.asia-southeast1.run.app" in html  # CTA
  assert "mailto:yaw2558@gmail.com" in html
  assert "../styles.css" in html  # shared brand stylesheet


def test_article_seo_and_cta():
  for slug in ARTICLES:
    html = (SITE_INDEX.parent / "blog" / slug).read_text(encoding="utf-8")
    assert "<h1>" in html, slug
    assert '<meta name="description"' in html, slug
    assert 'property="og:type" content="article"' in html, slug
    assert "application/ld+json" in html, slug  # Article schema
    assert "gateway-1008099094873.asia-southeast1.run.app" in html, slug  # CTA
    assert "<details" in html, slug  # FAQ accordions
    assert "../styles.css" in html, slug
  first = (SITE_INDEX.parent / "blog" / ARTICLES[0]).read_text(
    encoding="utf-8"
  )
  assert "HS Code" in first
  assert "customs.go.th" in first  # official-source link
