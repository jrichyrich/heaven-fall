(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./card_renderer"));
    return;
  }
  root.HeavenFallApp = factory(root.HeavenFallCardRenderer);
})(typeof globalThis !== "undefined" ? globalThis : this, function (renderer) {
  "use strict";

  function escapeHtml(value) {
    return renderer.escapeHtml(value);
  }

  function createInitialState(catalog) {
    const units = Array.isArray(catalog && catalog.units) ? catalog.units : [];
    return {
      viewMode: "units",
      previewMode: "digital",
      selectedUnitId: units.length ? units[0].unitId : null
    };
  }

  function reduceState(state, action, catalog) {
    const current = Object.assign({}, state);
    const units = Array.isArray(catalog && catalog.units) ? catalog.units : [];
    if (!action || !action.type) {
      return current;
    }

    if (action.type === "set-view-mode") {
      current.viewMode = action.value === "rules" ? "rules" : "units";
      return current;
    }

    if (action.type === "set-preview-mode") {
      current.previewMode = action.value === "source" ? "source" : "digital";
      return current;
    }

    if (action.type === "select-unit") {
      const nextId = String(action.value || "");
      current.selectedUnitId = units.some((unit) => unit.unitId === nextId)
        ? nextId
        : current.selectedUnitId;
      return current;
    }

    return current;
  }

  function getSelectedUnit(state, catalog) {
    const units = Array.isArray(catalog && catalog.units) ? catalog.units : [];
    return units.find((unit) => unit.unitId === state.selectedUnitId) || units[0] || null;
  }

  function renderViewToggle(state) {
    return `
      <div class="toggle-row">
        <button class="toggle-btn ${state.viewMode === "units" ? "is-active" : ""}" data-action="set-view-mode" data-value="units">Units</button>
        <button class="toggle-btn ${state.viewMode === "rules" ? "is-active" : ""}" data-action="set-view-mode" data-value="rules">Rules</button>
      </div>
    `;
  }

  function renderPreviewToggle(state) {
    return `
      <div class="toggle-row">
        <button class="toggle-btn ${state.previewMode === "digital" ? "is-active" : ""}" data-action="set-preview-mode" data-value="digital">Digital</button>
        <button class="toggle-btn ${state.previewMode === "source" ? "is-active" : ""}" data-action="set-preview-mode" data-value="source">Source</button>
      </div>
    `;
  }

  function summarizeUnit(unit) {
    const unresolved = unit && unit.verification && unit.verification.hasUnresolvedFields;
    const maxLabel = unit && unit.maxPerSquad != null ? `Max ${unit.maxPerSquad}` : "Max ?";
    return `
      <button class="unit-button" data-action="select-unit" data-value="${escapeHtml(unit.unitId)}">
        <span class="unit-name">${escapeHtml(unit.name)}</span>
        <span class="unit-meta">${escapeHtml(maxLabel)}</span>
        <div class="pill-row">
          ${unit.tags.map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("")}
          ${unresolved ? '<span class="pill pill-warn">Needs verification</span>' : ""}
        </div>
      </button>
    `;
  }

  function renderSidebar(state, manifest, catalog) {
    const units = Array.isArray(catalog && catalog.units) ? catalog.units : [];
    const rules = Array.isArray(catalog && catalog.rules) ? catalog.rules : [];
    const selected = getSelectedUnit(state, catalog);
    const unitButtons = units.map((unit) => {
      const html = summarizeUnit(unit);
      if (selected && unit.unitId === selected.unitId) {
        return html.replace('class="unit-button"', 'class="unit-button is-active"');
      }
      return html;
    }).join("");

    return `
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-kicker">Static Library</span>
          <h1>Heaven Fall</h1>
          <p>${escapeHtml((manifest && manifest.unitCount) || units.length)} unit cards. ${(manifest && manifest.rulesSectionCount) || 0} extracted rule sections.</p>
        </div>
        ${renderViewToggle(state)}
        ${state.viewMode === "units" ? `
          <section class="sidebar-panel">
            <span class="section-label">Units</span>
            <div class="unit-list">${unitButtons}</div>
          </section>
        ` : `
          <section class="sidebar-panel">
            <span class="section-label">Rule Groups</span>
            <div class="rule-list">
              ${rules.map((group) => `
                <a class="unit-button rule-anchor" href="#${escapeHtml(group.id)}">
                  <span class="unit-name">${escapeHtml(group.title)}</span>
                  <span class="rule-list-label">${escapeHtml(group.sections.length)} sections</span>
                </a>
              `).join("")}
            </div>
          </section>
        `}
      </aside>
    `;
  }

  function renderSourceCard(unit) {
    if (!unit) {
      return '<div class="empty-state">No unit selected.</div>';
    }
    return `
      <figure class="source-surface">
        <header class="source-header">
          <span class="section-label">Source Capture</span>
          <h2 class="rules-title">${escapeHtml(unit.name)}</h2>
        </header>
        <img src="${escapeHtml(unit.sourceImageUrl)}" alt="Source card for ${escapeHtml(unit.name)}">
        <p class="source-copy">Original photographed card used for the v1 transcription.</p>
      </figure>
    `;
  }

  function renderMain(state, catalog) {
    const selected = getSelectedUnit(state, catalog);
    if (state.viewMode === "rules") {
      return `
        <main class="main">
          <div class="main-card">
            <header class="view-header">
              <div>
                <span class="section-label">Rules View</span>
                <h2 class="view-title">Game Rules</h2>
                <p class="view-copy">Structured sections extracted from the Heaven Fall rules PDF.</p>
              </div>
            </header>
            ${renderer.renderRulesGroups(catalog.rules)}
          </div>
        </main>
      `;
    }

    return `
      <main class="main">
        <div class="main-card">
          <header class="view-header">
            <div>
              <span class="section-label">Unit Library</span>
              <h2 class="view-title">${selected ? escapeHtml(selected.name) : "No Unit Selected"}</h2>
              <p class="view-copy">Toggle between the rebuilt card and the original handwritten source photo.</p>
            </div>
            ${renderPreviewToggle(state)}
          </header>
          ${selected ? (state.previewMode === "source"
            ? renderSourceCard(selected)
            : renderer.renderDigitalCard(selected)) : '<div class="empty-state">No unit cards were found.</div>'}
        </div>
      </main>
    `;
  }

  function renderApp(rootElement, state, manifest, catalog) {
    rootElement.className = "";
    rootElement.innerHTML = `
      <div class="app-shell">
        ${renderSidebar(state, manifest, catalog)}
        ${renderMain(state, catalog)}
      </div>
    `;
  }

  async function loadJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to load ${url}: ${response.status}`);
    }
    return response.json();
  }

  async function boot() {
    const rootElement = document.getElementById("app");
    if (!rootElement) {
      return;
    }

    try {
      const [manifest, catalog] = await Promise.all([
        loadJson("./data/manifest.json"),
        loadJson("./data/catalog.json")
      ]);
      let state = createInitialState(catalog);
      renderApp(rootElement, state, manifest, catalog);
      rootElement.addEventListener("click", function (event) {
        const target = event.target && event.target.closest("[data-action]");
        if (!target) {
          return;
        }
        event.preventDefault();
        state = reduceState(state, {
          type: target.getAttribute("data-action"),
          value: target.getAttribute("data-value")
        }, catalog);
        renderApp(rootElement, state, manifest, catalog);
      });
    } catch (error) {
      rootElement.className = "app-error";
      rootElement.textContent = error instanceof Error ? error.message : String(error);
    }
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", boot);
  }

  return {
    boot,
    createInitialState,
    getSelectedUnit,
    reduceState,
    renderApp
  };
});
