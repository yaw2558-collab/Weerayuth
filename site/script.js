// Mobile nav toggle + footer year. No framework, no tracking.
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
  var y = document.getElementById("year");
  if (y) y.textContent = String(new Date().getFullYear());
})();
