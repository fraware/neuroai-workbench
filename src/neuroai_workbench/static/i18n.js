(() => {
  "use strict";

  function requestedLocale() {
    const params = new URLSearchParams(window.location.search);
    return params.get("lang") || navigator.language || "en";
  }

  function applyMessages(payload) {
    if (!payload || payload.translation_scope !== "PRESENTATION_ONLY" || !payload.messages) return;
    const messages = payload.messages;
    document.documentElement.lang = payload.locale || "en";
    document.documentElement.dataset.presentationLocale = payload.locale || "en";
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const key = element.getAttribute("data-i18n");
      if (key && Object.prototype.hasOwnProperty.call(messages, key)) {
        element.textContent = messages[key];
      }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      const key = element.getAttribute("data-i18n-placeholder");
      if (key && Object.prototype.hasOwnProperty.call(messages, key)) {
        element.setAttribute("placeholder", messages[key]);
      }
    });
  }

  async function initializePresentationLocale() {
    const locale = requestedLocale();
    try {
      const response = await fetch(`/api/presentation/catalog?locale=${encodeURIComponent(locale)}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      applyMessages(await response.json());
    } catch (_) {
      // Static English fallback text remains authoritative for presentation if the local catalog endpoint is unavailable.
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializePresentationLocale, { once: true });
  } else {
    initializePresentationLocale();
  }
})();
