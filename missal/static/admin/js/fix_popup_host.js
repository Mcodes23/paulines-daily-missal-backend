(function() {
  document.addEventListener("click", function (e) {
    const target = e.target.closest("a.related-lookup, a.add-another");
    if (!target) return;

    const currentHost = window.location.host;
    const href = target.getAttribute("href");

    if (href && href.includes("localhost")) {
      target.setAttribute("href", href.replace("localhost:8000", currentHost));
    }
  });
})();
