const test = require("node:test");
const assert = require("node:assert/strict");

const renderer = require("../docs/card_renderer");
const app = require("../docs/app");

test("renderDigitalCard preserves six-stat order and shows points", () => {
  const html = renderer.renderDigitalCard({
    unitId: "pistolier",
    name: "Pistolier",
    points: 10,
    maxPerSquad: 3,
    stats: [
      { key: "m", label: "M", value: '7"' },
      { key: "w", label: "W", value: 4 },
      { key: "sv", label: "SV", value: "4+" },
      { key: "t", label: "T", value: 4 },
      { key: "sd", label: "SD", value: 3 },
      { key: "stm", label: "STM", value: 2 }
    ],
    defense: [],
    attacks: [],
    tags: [],
    specialRules: [],
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
  assert.deepEqual(labels.slice(0, 6), ["M", "W", "SV", "T", "SD", "STM"]);
  assert.match(html, /10 pts/);
});

test("renderDigitalCard renders special rules and hides empty defense", () => {
  const html = renderer.renderDigitalCard({
    unitId: "champion",
    name: "Champion",
    points: 20,
    maxPerSquad: null,
    stats: [],
    defense: [],
    attacks: [],
    tags: ["Leader"],
    specialRules: ["Warcry: Once per game when this model destroys your opponent's Leader model."],
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

  assert.match(html, /Special Rules/);
  assert.match(html, /Warcry/);
  assert.doesNotMatch(html, /<h2 class="section-heading">Defense<\/h2>/);
});

test("reduceState keeps the selected unit when preview mode changes", () => {
  const catalog = {
    units: [
      { unitId: "pistolier" },
      { unitId: "lwbt-heavy-weapon" }
    ]
  };
  let state = app.createInitialState(catalog);
  state = app.reduceState(state, { type: "select-unit", value: "lwbt-heavy-weapon" }, catalog);
  state = app.reduceState(state, { type: "set-preview-mode", value: "source" }, catalog);

  assert.equal(state.selectedUnitId, "lwbt-heavy-weapon");
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

test("hash helpers preserve unit, preview, and review state for deep links", () => {
  const state = {
    viewMode: "review",
    previewMode: "source",
    selectedUnitId: "champion",
    reviewStatusFilter: "verified",
    reviewSourceQualityFilter: "good",
    sourceZoom: 1.5
  };

  const hash = app.buildHashFromState(state);
  const parsed = app.parseHashState(hash);

  assert.equal(parsed.viewMode, "review");
  assert.equal(parsed.previewMode, "source");
  assert.equal(parsed.selectedUnitId, "champion");
  assert.equal(parsed.reviewStatusFilter, "verified");
  assert.equal(parsed.reviewSourceQualityFilter, "good");
  assert.equal(parsed.sourceZoom, 1.5);
});

test("createInitialState accepts factions as a top-level view", () => {
  const catalog = {
    units: [{ unitId: "champion" }],
    factions: [{ id: "houno", title: "Houno", sections: [] }]
  };

  const state = app.createInitialState(catalog, "#view=factions&unit=champion");

  assert.equal(state.viewMode, "factions");
  assert.equal(state.selectedUnitId, "champion");
});
