const test = require("node:test");
const assert = require("node:assert/strict");

const renderer = require("../docs/card_renderer");
const app = require("../docs/app");

test("renderDigitalCard preserves stat order from the source array", () => {
  const html = renderer.renderDigitalCard({
    unitId: "test-unit",
    name: "Test Unit",
    maxPerSquad: 2,
    stats: [
      { key: "stm", label: "STM", value: 3 },
      { key: "w", label: "W", value: 4 },
      { key: "m", label: "M", value: 7 }
    ],
    defense: [],
    attacks: [],
    tags: [],
    rulesText: [],
    verification: { hasUnresolvedFields: false, unresolvedFields: [], notes: [] }
  });

  const labels = [...html.matchAll(/<span class="chip-label">([^<]+)<\/span>/g)].map((match) => match[1]);
  assert.deepEqual(labels, ["STM", "W", "M"]);
});

test("renderDigitalCard hides empty sections and shows the verification badge", () => {
  const html = renderer.renderDigitalCard({
    unitId: "test-unit",
    name: "Test Unit",
    maxPerSquad: null,
    stats: [],
    defense: [],
    attacks: [],
    tags: [],
    rulesText: [],
    verification: {
      hasUnresolvedFields: true,
      unresolvedFields: ["stats[0].value"],
      notes: ["Needs review"]
    }
  });

  assert.match(html, /Needs Verification/);
  assert.doesNotMatch(html, /<h2 class="section-heading">Attacks<\/h2>/);
  assert.doesNotMatch(html, /<h2 class="section-heading">Defense<\/h2>/);
});

test("reduceState keeps the selected unit when preview mode changes", () => {
  const catalog = {
    units: [
      { unitId: "pistollier" },
      { unitId: "gunner" }
    ]
  };
  let state = app.createInitialState(catalog);
  state = app.reduceState(state, { type: "select-unit", value: "gunner" }, catalog);
  state = app.reduceState(state, { type: "set-preview-mode", value: "source" }, catalog);

  assert.equal(state.selectedUnitId, "gunner");
  assert.equal(state.previewMode, "source");
});
