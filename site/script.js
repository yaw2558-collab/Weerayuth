// Mobile nav toggle + footer year + TH/EN language toggle. No framework, no tracking.
(function () {
  var btn = document.getElementById("menubtn");
  var nav = document.getElementById("nav");
  if (btn && nav) {
    btn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.addEventListener("click", function (e) {
      if (e.target.tagName === "A") nav.classList.remove("open");
    });
  }

  // ---- i18n: page default is Thai; EN strings below, TH restored from originals ----
  var EN = {
    _title: "ซอฟแวร์ดีดี — Thai customs HS adviser powered by AI",
    _desc: "ThaiCustoms — AI that finds HS codes, import duty and FTA benefits for Thai importers. Use on the web or download the desktop app.",
    brand_sub: "Import–export helper apps",
    menu_main: "Main menu",
    menu_foot: "Footer menu",
    menu_open: "Open menu",
    mock_label: "Usage example",
    nav_product: "Products",
    nav_pricing: "Pricing",
    nav_how: "How it works",
    nav_download: "Download",
    nav_faq: "FAQ",
    nav_contact: "Contact",
    cta_start: "Get started",
    hero_h1: "Thai customs HS answers<br>in minutes, powered by AI",
    hero_lede: "<strong>ThaiCustoms</strong> finds HS codes, import duty, FTA benefits and related documents — just type your question and attach product photos or files.",
    hero_cta_web: "Start on the web",
    hero_cta_dl: "Download the app",
    hero_trial: "Free sign-up with 30 trial credits · No card required",
    mock_q: "How much duty to import Bluetooth speakers from China?",
    mock_a_title: "Answer summary",
    mock_a1: "Relevant HS codes",
    mock_a2: "MFN import duty rates",
    mock_a3: "FTA benefits that cut duty",
    mock_a4: "Licences & documents to prepare",
    mock_a_src: "Sourced, with official links on every point",
    mock_cap: "Sample answer outline — details depend on your product",
    product_h2: "Our products",
    product_sub: "One app for now — click to start using it right away",
    product_h3: "ThaiCustoms — Thai customs adviser",
    product_tag: "AI Q&A for importers: codes, duty, privileges and paperwork",
    feat1: "Find HS codes with interpretation rules (GRI)",
    feat2: "Check MFN duty rates and FTA benefits (ASEAN, China, Japan and more)",
    feat3: "Lists licences and documents needed before importing",
    feat4: "Attach product photos, labels, invoices or Excel/PDF files (up to 20MB)",
    feat5: "Remembers conversation context — ask follow-ups freely",
    feat6: "Every answer cites sources and official links",
    product_open: "Open web app",
    manual_th: "Thai manual (PDF)",
    side_who: "Who it's for",
    side_who1: "Importers/exporters who want duty costs up front",
    side_who2: "Brokers and agents who need fast HS lookups",
    side_who3: "Purchasers comparing products across countries",
    side_how: "Two ways to use it",
    side_how1: "<strong>On the web</strong> — open your browser and start",
    side_how2: "<strong>Desktop app</strong> — one icon on Windows and Mac",
    pricing_h2: "Credit pricing",
    pricing_sub: "1 question = 10 credits (attachments included) · Pay by card via Stripe, credits arrive instantly",
    credits_word: "credits",
    price1_p: "10 questions",
    price2_flag: "Most popular",
    price2_p: "50 questions · ≈ ฿9 each",
    price3_p: "100 questions · ≈ ฿8 each",
    price_cta: "Start free first",
    pricing_trial: "New users get 30 free trial credits (3 questions) · We never store your card number",
    how_h2: "Get started in 4 steps",
    step1_t: "Sign up / Log in",
    step1_d: "With Google or email — get 30 trial credits instantly",
    step2_t: "Accept data consent",
    step2_d: "Just once, so we can log Q&A to improve the service",
    step3_t: "Type your question",
    step3_d: "The clearer the details (product type, materials, origin country), the better the answer. Photos and files welcome.",
    step4_t: "Top up when you run out",
    step4_d: "Pick a package, pay via Stripe, credits arrive instantly — keep asking right away",
    dl_h2: "Download the desktop app",
    dl_sub: "One icon on your machine that opens the web app in your browser — current version <strong>v1.0.1</strong>",
    dl_win_p: ".exe installer (about 2MB), no admin rights needed<br>On first launch SmartScreen may appear → click <em>More info → Run anyway</em>",
    dl_win_btn: "Download for Windows",
    dl_mac_p: ".dmg file — drag the app into Applications<br>First time, <strong>right-click the app → Open</strong> (once only, then it opens normally)",
    dl_mac_btn: "Download for Mac",
    dl_all: "See all releases →",
    faq_h2: "Frequently asked questions",
    faq1_q: "Do I need to install anything?",
    faq1_a: "No — open the web app in your browser and start. The installer is just for people who want a one-click desktop icon.",
    faq2_q: "I paid but got no credits. What now?",
    faq2_a: "Wait a moment, then refresh the page. If credits still don't show, message us on LINE with your sign-up email.",
    faq3_q: "I see “insufficient_credits” / “too fast”?",
    faq3_a: "<em>insufficient_credits</em> means fewer than 10 credits left — top up first. <em>too fast</em> means slow down — wait about 20 seconds and resend.",
    faq4_q: "What files can I attach?",
    faq4_a: "Images (JPG/PNG), spreadsheets (.xlsx/.xls), documents (.pdf/.docx) and text (.csv/.txt), up to 20MB per file.",
    faq5_q: "How reliable are the answers?",
    faq5_a: "The AI summarises official sources and links references every time, but treat answers as preliminary — verify with the Customs Department or your broker before acting.",
    contact_h2: "Talk to us",
    contact_sub: "Questions about usage, top-ups, or import work — message us anytime",
    contact_mail: "Email",
    foot_manual: "Manual (PDF)",
    copy: "© {Y} ซอฟแวร์ดีดี · AI answers are preliminary guidance only"
  };
  var KEY = "tc-lang";
  var YEAR = String(new Date().getFullYear());
  var origTitle = document.title;
  var metaDesc = document.querySelector('meta[name="description"]');
  var origDesc = metaDesc ? metaDesc.getAttribute("content") : "";
  function lang() { try { return localStorage.getItem(KEY) === "en" ? "en" : "th"; } catch (e) { return "th"; } }
  function setText(el, v) { if (el.dataset.iorig == null) el.dataset.iorig = el.textContent; el.textContent = v == null ? el.dataset.iorig : v; }
  function setHtml(el, v) { if (el.dataset.iohtml == null) el.dataset.iohtml = el.innerHTML; el.innerHTML = v == null ? el.dataset.iohtml : v.split("{Y}").join(YEAR); }
  function setAttr(el, attr, store, v) { if (el.dataset[store] == null) el.dataset[store] = el.getAttribute(attr) || ""; el.setAttribute(attr, v == null ? el.dataset[store] : v); }
  function applyLang(lg) {
    var en = lg === "en";
    document.querySelectorAll("[data-i18n]").forEach(function (el) { setText(el, en ? EN[el.getAttribute("data-i18n")] : null); });
    document.querySelectorAll("[data-i18n-html]").forEach(function (el) { setHtml(el, en ? EN[el.getAttribute("data-i18n-html")] : null); });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) { setAttr(el, "aria-label", "ioaria", en ? EN[el.getAttribute("data-i18n-aria")] : null); });
    document.title = en ? EN._title : origTitle;
    if (metaDesc) metaDesc.setAttribute("content", en ? EN._desc : origDesc);
    document.documentElement.setAttribute("lang", en ? "en" : "th");
    var lb = document.getElementById("langbtn");
    if (lb) lb.textContent = en ? "TH" : "EN";
    try { localStorage.setItem(KEY, lg); } catch (e) {}
    var y = document.getElementById("year");
    if (y) y.textContent = YEAR;
  }
  var lb = document.getElementById("langbtn");
  if (lb) lb.addEventListener("click", function () { applyLang(lang() === "en" ? "th" : "en"); });
  applyLang(lang());
})();
