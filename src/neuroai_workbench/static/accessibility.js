(() => {
  "use strict";

  function applyTabState(tabs, panels, name, moveFocus = false) {
    let selectedTab = null;
    for (const tab of tabs) {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
      tab.tabIndex = active ? 0 : -1;
      if (active) selectedTab = tab;
    }
    for (const panel of panels) {
      panel.hidden = panel.id !== `tab-${name}`;
    }
    if (moveFocus && selectedTab) selectedTab.focus();
    return selectedTab;
  }

  function nextTabIndex(currentIndex, key, length) {
    if (length <= 0 || currentIndex < 0 || currentIndex >= length) return null;
    if (key === "ArrowRight") return (currentIndex + 1) % length;
    if (key === "ArrowLeft") return (currentIndex - 1 + length) % length;
    if (key === "Home") return 0;
    if (key === "End") return length - 1;
    return null;
  }

  function focusSkipTarget(link, event, root) {
    const href = link.getAttribute("href");
    const target = href && href.length > 1 ? root.getElementById(href.slice(1)) : null;
    if (!target) return false;
    event.preventDefault();
    target.focus();
    target.scrollIntoView({ block: "start" });
    return true;
  }

  function publishToastAnnouncement(toast, statusRegion, alertRegion, schedule, state) {
    if (toast.hidden) return false;
    const message = toast.textContent.trim();
    if (!message) return false;

    const region = toast.classList.contains("error") ? alertRegion : statusRegion;
    state.sequence += 1;
    const currentSequence = state.sequence;
    region.textContent = "";
    schedule(() => {
      if (currentSequence === state.sequence) region.textContent = message;
    });
    return true;
  }

  function initializeTabList(tablist) {
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    const panels = tabs
      .map((tab) => document.getElementById(tab.getAttribute("aria-controls")))
      .filter((panel) => panel !== null);
    if (!tabs.length) return;

    const selected = tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
    applyTabState(tabs, panels, selected.dataset.tab);

    tablist.addEventListener("click", (event) => {
      const tab = event.target.closest?.('[role="tab"]');
      if (!tab || !tablist.contains(tab)) return;
      applyTabState(tabs, panels, tab.dataset.tab);
    });

    tablist.addEventListener("keydown", (event) => {
      const tab = event.target.closest?.('[role="tab"]');
      if (!tab || !tablist.contains(tab)) return;
      const currentIndex = tabs.indexOf(tab);
      const destinationIndex = nextTabIndex(currentIndex, event.key, tabs.length);
      if (destinationIndex === null) return;
      event.preventDefault();
      applyTabState(tabs, panels, tabs[destinationIndex].dataset.tab, true);
    });
  }

  function initializeSkipLinks() {
    for (const link of document.querySelectorAll('.skip-link[href^="#"]')) {
      link.addEventListener("click", (event) => {
        focusSkipTarget(link, event, document);
      });
    }
  }

  function initializeToastAnnouncements() {
    const statusRegion = document.querySelector('[data-announcer="status"]');
    const alertRegion = document.querySelector('[data-announcer="alert"]');
    if (!statusRegion || !alertRegion) return;

    const state = { sequence: 0 };
    const scheduleAnnouncement = (callback) => window.setTimeout(callback, 0);

    for (const toast of document.querySelectorAll("[data-toast-announcer]")) {
      let queued = false;

      const publish = () => {
        queued = false;
        publishToastAnnouncement(toast, statusRegion, alertRegion, scheduleAnnouncement, state);
      };

      const schedule = () => {
        if (queued) return;
        queued = true;
        queueMicrotask(publish);
      };

      new MutationObserver(schedule).observe(toast, {
        attributes: true,
        attributeFilter: ["hidden", "class"],
        childList: true,
        characterData: true,
        subtree: true,
      });
      publish();
    }
  }

  function initialize() {
    initializeSkipLinks();
    for (const tablist of document.querySelectorAll('[role="tablist"]')) initializeTabList(tablist);
    initializeToastAnnouncements();
  }

  globalThis.NeuroAIAccessibility = Object.freeze({
    applyTabState,
    focusSkipTarget,
    nextTabIndex,
    publishToastAnnouncement,
  });

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initialize, { once: true });
    } else {
      initialize();
    }
  }
})();
