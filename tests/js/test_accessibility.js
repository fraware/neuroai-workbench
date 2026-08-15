"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.join(__dirname, "../../src/neuroai_workbench/static/accessibility.js"),
  "utf8",
);
const context = { globalThis: {} };
vm.createContext(context);
vm.runInContext(source, context);
const {
  applyTabState,
  focusSkipTarget,
  nextTabIndex,
  publishToastAnnouncement,
} = context.globalThis.NeuroAIAccessibility;

function fakeClassList(initial = []) {
  const classes = new Set(initial);
  return {
    toggle(value, enabled) {
      if (enabled) classes.add(value);
      else classes.delete(value);
    },
    contains(value) {
      return classes.has(value);
    },
  };
}

function fakeTab(name) {
  const attributes = new Map();
  return {
    dataset: { tab: name },
    classList: fakeClassList(),
    setAttribute(attributeName, value) {
      attributes.set(attributeName, value);
    },
    getAttribute(attributeName) {
      return attributes.get(attributeName);
    },
    tabIndex: -1,
    focused: false,
    focus() {
      this.focused = true;
    },
  };
}

function fakeToast(message, { error = false, hidden = false } = {}) {
  return {
    hidden,
    textContent: message,
    classList: fakeClassList(error ? ["error"] : []),
  };
}

test("tab destination keys wrap and ignore unrelated input", () => {
  assert.equal(nextTabIndex(0, "ArrowRight", 3), 1);
  assert.equal(nextTabIndex(2, "ArrowRight", 3), 0);
  assert.equal(nextTabIndex(0, "ArrowLeft", 3), 2);
  assert.equal(nextTabIndex(1, "Home", 3), 0);
  assert.equal(nextTabIndex(1, "End", 3), 2);
  assert.equal(nextTabIndex(1, "Enter", 3), null);
  assert.equal(nextTabIndex(-1, "ArrowRight", 3), null);
  assert.equal(nextTabIndex(0, "ArrowRight", 0), null);
});

test("tab activation synchronizes CSS, ARIA, roving tabindex, panels, and focus", () => {
  const tabs = [fakeTab("summary"), fakeTab("requirements"), fakeTab("events")];
  const panels = [
    { id: "tab-summary", hidden: false },
    { id: "tab-requirements", hidden: true },
    { id: "tab-events", hidden: true },
  ];

  const selected = applyTabState(tabs, panels, "requirements", true);

  assert.equal(selected, tabs[1]);
  assert.equal(tabs[0].classList.contains("active"), false);
  assert.equal(tabs[1].classList.contains("active"), true);
  assert.equal(tabs[0].getAttribute("aria-selected"), "false");
  assert.equal(tabs[1].getAttribute("aria-selected"), "true");
  assert.equal(tabs[0].tabIndex, -1);
  assert.equal(tabs[1].tabIndex, 0);
  assert.equal(tabs[1].focused, true);
  assert.equal(panels[0].hidden, true);
  assert.equal(panels[1].hidden, false);
  assert.equal(panels[2].hidden, true);
});

test("activation tolerates an unknown tab name without granting focus", () => {
  const tabs = [fakeTab("summary")];
  const panels = [{ id: "tab-summary", hidden: false }];
  assert.equal(applyTabState(tabs, panels, "missing", true), null);
  assert.equal(tabs[0].getAttribute("aria-selected"), "false");
  assert.equal(tabs[0].tabIndex, -1);
  assert.equal(panels[0].hidden, true);
});

test("skip navigation prevents default, focuses the target, and scrolls it into view", () => {
  const target = {
    focused: false,
    scrollOptions: null,
    focus() {
      this.focused = true;
    },
    scrollIntoView(options) {
      this.scrollOptions = options;
    },
  };
  const link = { getAttribute: () => "#main-content" };
  const root = { getElementById: (id) => (id === "main-content" ? target : null) };
  const event = {
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };

  assert.equal(focusSkipTarget(link, event, root), true);
  assert.equal(event.prevented, true);
  assert.equal(target.focused, true);
  assert.equal(target.scrollOptions.block, "start");
});

test("skip navigation leaves the browser default intact when the target is missing", () => {
  const link = { getAttribute: () => "#missing" };
  const root = { getElementById: () => null };
  const event = {
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };

  assert.equal(focusSkipTarget(link, event, root), false);
  assert.equal(event.prevented, false);
});

test("routine and error toasts route to distinct announcement regions", () => {
  const statusRegion = { textContent: "old status" };
  const alertRegion = { textContent: "old alert" };
  const callbacks = [];
  const schedule = (callback) => callbacks.push(callback);
  const state = { sequence: 0 };

  assert.equal(
    publishToastAnnouncement(fakeToast("Saved"), statusRegion, alertRegion, schedule, state),
    true,
  );
  assert.equal(statusRegion.textContent, "");
  assert.equal(alertRegion.textContent, "old alert");
  callbacks.shift()();
  assert.equal(statusRegion.textContent, "Saved");

  assert.equal(
    publishToastAnnouncement(fakeToast("Save failed", { error: true }), statusRegion, alertRegion, schedule, state),
    true,
  );
  assert.equal(alertRegion.textContent, "");
  callbacks.shift()();
  assert.equal(alertRegion.textContent, "Save failed");
});

test("repeated identical announcements clear and republish the same message", () => {
  const statusRegion = { textContent: "" };
  const alertRegion = { textContent: "" };
  const callbacks = [];
  const schedule = (callback) => callbacks.push(callback);
  const state = { sequence: 0 };
  const toast = fakeToast("Updated");

  publishToastAnnouncement(toast, statusRegion, alertRegion, schedule, state);
  callbacks.shift()();
  assert.equal(statusRegion.textContent, "Updated");

  publishToastAnnouncement(toast, statusRegion, alertRegion, schedule, state);
  assert.equal(statusRegion.textContent, "");
  callbacks.shift()();
  assert.equal(statusRegion.textContent, "Updated");
});

test("newer announcements suppress stale scheduled callbacks", () => {
  const statusRegion = { textContent: "" };
  const alertRegion = { textContent: "" };
  const callbacks = [];
  const schedule = (callback) => callbacks.push(callback);
  const state = { sequence: 0 };
  const toast = fakeToast("First");

  publishToastAnnouncement(toast, statusRegion, alertRegion, schedule, state);
  toast.textContent = "Second";
  publishToastAnnouncement(toast, statusRegion, alertRegion, schedule, state);

  callbacks[0]();
  assert.equal(statusRegion.textContent, "");
  callbacks[1]();
  assert.equal(statusRegion.textContent, "Second");
});

test("hidden or empty toasts do not schedule announcements", () => {
  const statusRegion = { textContent: "status" };
  const alertRegion = { textContent: "alert" };
  const callbacks = [];
  const schedule = (callback) => callbacks.push(callback);
  const state = { sequence: 0 };

  assert.equal(
    publishToastAnnouncement(fakeToast("Hidden", { hidden: true }), statusRegion, alertRegion, schedule, state),
    false,
  );
  assert.equal(
    publishToastAnnouncement(fakeToast("   "), statusRegion, alertRegion, schedule, state),
    false,
  );
  assert.equal(callbacks.length, 0);
  assert.equal(state.sequence, 0);
  assert.equal(statusRegion.textContent, "status");
  assert.equal(alertRegion.textContent, "alert");
});
