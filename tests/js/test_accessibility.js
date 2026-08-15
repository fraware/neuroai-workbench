"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(
  path.join(__dirname, "../../src/neuroai_workbench/static/accessibility.js"),
  "utf8",
);
const context = { globalThis: {} };
vm.createContext(context);
vm.runInContext(source, context);
const { applyTabState, nextTabIndex } = context.globalThis.NeuroAIAccessibility;

function fakeTab(name) {
  const classes = new Set();
  const attributes = new Map();
  return {
    dataset: { tab: name },
    classList: {
      toggle(value, enabled) {
        if (enabled) classes.add(value);
        else classes.delete(value);
      },
      contains(value) {
        return classes.has(value);
      },
    },
    setAttribute(name, value) {
      attributes.set(name, value);
    },
    getAttribute(name) {
      return attributes.get(name);
    },
    tabIndex: -1,
    focused: false,
    focus() {
      this.focused = true;
    },
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
