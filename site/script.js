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
  var ZH = {
    _title: "ซอฟแวร์ดีดี — 泰国海关HS顾问",
    _desc: "ThaiCustoms — 帮助泰国进口商查找HS编码、进口关税和FTA优惠的AI。可在网页使用或下载桌面应用。",
    brand_sub: "进出口助手应用",
    menu_main: "主菜单",
    menu_foot: "页脚菜单",
    menu_open: "打开菜单",
    mock_label: "使用示例",
    nav_product: "产品",
    nav_pricing: "价格",
    nav_how: "使用方法",
    nav_download: "下载",
    nav_faq: "常见问题",
    nav_contact: "联系我们",
    cta_start: "开始使用",
    hero_h1: "泰国海关HS问答<br>几分钟搞定，AI驱动",
    hero_lede: "<strong>ThaiCustoms</strong>帮您查找HS编码、进口关税、FTA优惠及相关单证——只需输入问题，还可附上产品照片或文件。",
    hero_cta_web: "在网页上开始",
    hero_cta_dl: "下载应用",
    hero_trial: "免费注册即得30试用积分 · 无需绑卡",
    mock_q: "从中国进口蓝牙音箱要交多少关税？",
    mock_a_title: "答案概要",
    mock_a1: "相关HS编码",
    mock_a2: "MFN进口税率",
    mock_a3: "可减免关税的FTA优惠",
    mock_a4: "需准备的许可证和单证",
    mock_a_src: "每条都有来源和官方链接",
    mock_cap: "答案结构示例——详情取决于您的产品",
    product_h2: "我们的产品",
    product_sub: "目前只有1款应用——点击即可立即使用",
    product_h3: "ThaiCustoms — 泰国海关顾问",
    product_tag: "面向进口商的AI问答：编码、关税、优惠和单证",
    feat1: "查找HS编码及归类总规则(GRI)",
    feat2: "查询MFN进口税率和FTA优惠（东盟、中国、日本等）",
    feat3: "列出进口前所需的许可证和单证",
    feat4: "提问时可附上产品照片、标签、发票或Excel/PDF文件（最大20MB）",
    feat5: "记住对话上下文——可随时追问",
    feat6: "每个回答都注明来源和官方链接",
    product_open: "打开网页应用",
    manual_th: "泰语手册(PDF)",
    side_who: "适用人群",
    side_who1: "想提前知道关税成本的进出口商",
    side_who2: "需要快速查编码的报关代理",
    side_who3: "需要比较多国产品价格的采购人员",
    side_how: "两种使用方式",
    side_how1: "<strong>网页版</strong>——打开浏览器即用",
    side_how2: "<strong>桌面版</strong>——Windows和Mac各一个图标",
    pricing_h2: "积分价格",
    pricing_sub: "提问1次 = 10积分（含附件）· 通过Stripe刷卡支付，积分即时到账",
    credits_word: "积分",
    price1_p: "可提10个问题",
    price2_flag: "最受欢迎",
    price2_p: "可提50个问题 · 每题约฿9",
    price3_p: "可提100个问题 · 每题约฿8",
    price_cta: "先免费试用",
    pricing_trial: "新用户免费获得30试用积分（可提3个问题）· 我们绝不保存您的卡号",
    how_h2: "4步轻松上手",
    step1_t: "注册 / 登录",
    step1_d: "使用Google或邮箱——即时获得30试用积分",
    step2_t: "同意数据授权",
    step2_d: "只需一次，以便我们记录问答来改进服务",
    step3_t: "输入您的问题",
    step3_d: "详情越清楚（产品种类、材质、原产国），回答越准确。欢迎添加图片或文件。",
    step4_t: "积分用完再充值",
    step4_d: "选择套餐，通过Stripe支付，积分即时到账——马上继续提问",
    dl_h2: "下载桌面应用",
    dl_sub: "电脑上一个图标，点击即在浏览器中打开网页应用——当前版本 <strong>v1.0.1</strong>",
    dl_win_p: ".exe安装包（约2MB），无需管理员权限<br>首次打开可能会出现SmartScreen → 点击<em>More info → Run anyway</em>",
    dl_win_btn: "下载Windows版",
    dl_mac_p: ".dmg文件——把应用拖入Applications文件夹<br>首次请<strong>右键点击应用 → Open</strong>（只需一次，之后正常打开）",
    dl_mac_btn: "下载Mac版",
    dl_all: "查看所有版本 →",
    faq_h2: "常见问题",
    faq1_q: "需要先安装吗？",
    faq1_a: "不需要——在浏览器中打开网页应用即可使用。安装包只是给想要一键桌面图标的人准备的。",
    faq2_q: "付款后没到账怎么办？",
    faq2_a: "请稍等片刻后刷新页面。如果积分仍未到账，请通过LINE联系我们并告知注册邮箱。",
    faq3_q: "看到“insufficient_credits”/“too fast”？",
    faq3_a: "<em>insufficient_credits</em>表示剩余积分不足10分，请先充值 · <em>too fast</em>表示发送太频繁，请等待约20秒后重试",
    faq4_q: "可以添加什么附件？",
    faq4_a: "图片（JPG/PNG）、电子表格（.xlsx/.xls）、文档（.pdf/.docx）和文本（.csv/.txt），单个文件最大20MB。",
    faq5_q: "回答有多可靠？",
    faq5_a: "AI基于官方来源总结，每次都附上引用链接，但请视为初步参考——采取行动前请与泰国海关或报关代理核实。",
    contact_h2: "联系我们",
    contact_sub: "使用、充值或进口业务有疑问——随时联系我们",
    contact_mail: "邮箱",
    foot_manual: "使用手册(PDF)",
    copy: "© {Y} ซอฟแวร์ดีดี · AI回答仅供初步参考"
  };
  var KEY = "tc-lang";
  var YEAR = String(new Date().getFullYear());
  var origTitle = document.title;
  var metaDesc = document.querySelector('meta[name="description"]');
  var origDesc = metaDesc ? metaDesc.getAttribute("content") : "";
  function lang() { try { var v = localStorage.getItem(KEY); return v === "en" || v === "zh" ? v : "th"; } catch (e) { return "th"; } }
  function nextLang(lg) { return lg === "th" ? "en" : lg === "en" ? "zh" : "th"; }
  function langLabel(lg) { return lg === "th" ? "EN" : lg === "en" ? "中文" : "TH"; }
  function setText(el, v) { if (el.dataset.iorig == null) el.dataset.iorig = el.textContent; el.textContent = v == null ? el.dataset.iorig : v; }
  function setHtml(el, v) { if (el.dataset.iohtml == null) el.dataset.iohtml = el.innerHTML; el.innerHTML = v == null ? el.dataset.iohtml : v.split("{Y}").join(YEAR); }
  function setAttr(el, attr, store, v) { if (el.dataset[store] == null) el.dataset[store] = el.getAttribute(attr) || ""; el.setAttribute(attr, v == null ? el.dataset[store] : v); }
  function applyLang(lg) {
    var D = lg === "en" ? EN : lg === "zh" ? ZH : null;
    document.querySelectorAll("[data-i18n]").forEach(function (el) { setText(el, D ? D[el.getAttribute("data-i18n")] : null); });
    document.querySelectorAll("[data-i18n-html]").forEach(function (el) { setHtml(el, D ? D[el.getAttribute("data-i18n-html")] : null); });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) { setAttr(el, "aria-label", "ioaria", D ? D[el.getAttribute("data-i18n-aria")] : null); });
    document.title = D ? D._title : origTitle;
    if (metaDesc) metaDesc.setAttribute("content", D ? D._desc : origDesc);
    document.documentElement.setAttribute("lang", lg === "zh" ? "zh-CN" : lg);
    var lb = document.getElementById("langbtn");
    if (lb) lb.textContent = langLabel(lg);
    try { localStorage.setItem(KEY, lg); } catch (e) {}
    var y = document.getElementById("year");
    if (y) y.textContent = YEAR;
  }
  var lb = document.getElementById("langbtn");
  if (lb) lb.addEventListener("click", function () { applyLang(nextLang(lang())); });
  applyLang(lang());
})();
