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
    verification: {
      status: "verified",
      statusLabel: "Verified",
      sourceQuality: "good",
      updatedAt: "2026-04-01T20:00:00+00:00",
      hasUnresolvedFields: false,
      unresolvedFields: [],
      notes: [],
      fieldNotes: {},
      reviewChecklist: { stats: true, defense: true, attacks: true, tags: true, rulesText: true },
      progress: { completed: 5, total: 5 }
    }
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
      status: "in_review",
      statusLabel: "Needs review",
      sourceQuality: "fair",
      updatedAt: "2026-04-01T20:00:00+00:00",
      hasUnresolvedFields: true,
      unresolvedFields: ["stats[0].value"],
      notes: ["Needs review"],
      fieldNotes: { "stats[0].value": "Number is obscured." },
      reviewChecklist: { stats: false, defense: true, attacks: true, tags: true, rulesText: true },
      progress: { completed: 4, total: 5 }
    }
  });

  assert.match(html, /Needs review/);
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

test("getVisibleUnits filters review mode by verification status and quality", () => {
  const catalog = {
    units: [
      { unitId: "a", verification: { status: "in_review", sourceQuality: "poor" } },
      { unitId: "b", verification: { status: "verified", sourceQuality: "good" } },
      { unitId: "c", verification: { status: "in_review", sourceQuality: "fair" } }
    ]
  };
  let state = app.createInitialState(catalog);
  state = app.reduceState(state, { type: "set-view-mode", value: "review" }, catalog);
  state = app.reduceState(state, { type: "set-review-status-filter", value: "in_review" }, catalog);
  state = app.reduceState(state, { type: "set-review-source-quality-filter", value: "fair" }, catalog);

  assert.deepEqual(app.getVisibleUnits(state, catalog).map((unit) => unit.unitId), ["c"]);
});

test("hash helpers preserve unit and review state for deep links", () => {
  const state = {
    viewMode: "review",
    previewMode: "digital",
    selectedUnitId: "champion",
    reviewStatusFilter: "in_review",
    reviewSourceQualityFilter: "poor",
    sourceZoom: 1.5
  };

  const hash = app.buildHashFromState(state);
  const parsed = app.parseHashState(hash);

  assert.equal(parsed.viewMode, "review");
  assert.equal(parsed.selectedUnitId, "champion");
  assert.equal(parsed.reviewStatusFilter, "in_review");
  assert.equal(parsed.reviewSourceQualityFilter, "poor");
  assert.equal(parsed.sourceZoom, 1.5);
});
