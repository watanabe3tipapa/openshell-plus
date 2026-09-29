(function () {
  "use strict";

  var links = window.OSUI_LINKS || {};

  document.querySelectorAll("[data-link]").forEach(function (el) {
    var url = links[el.getAttribute("data-link")];
    if (!url) {
      // 未設定のリンクは HTML 側のフォールバック（同一ページ内アンカーなど）をそのまま使う
      return;
    }
    el.setAttribute("href", url);
    if (/^https?:\/\//.test(url) && url.indexOf(location.origin) !== 0) {
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener");
    } else {
      el.removeAttribute("target");
      el.removeAttribute("rel");
    }
  });
})();
