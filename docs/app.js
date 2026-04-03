(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./card_renderer"));
    return;
  }
  root.HeavenFallApp = factory(root.HeavenFallCardRenderer);
})(typeof globalThis !== "undefined" ? globalThis : this, function (renderer) {
  "use strict";

  const DEFAULT_ZOOM = 1;
  const MIN_ZOOM = 1;
  const MAX_ZOOM = 3;
  const ZOOM_STEP = 0.25;

  function escapeHtml(value) {
    return renderer.escapeHtml(value);
  }

  function clampZoom(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return DEFAULT_ZOOM;
    }
    return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(numeric * 100) / 100));
  }

  function parseHashState(hashValue) {
    const rawHash = String(hashValue || "").replace(/^#/, "");
    if (!rawHash || !rawHash.includes("=")) {
      return {
        viewMode: null,
        previewMode: null,
        selectedUnitId: null,
        reviewStatusFilter: null,
        reviewSourceQualityFilter: null,
        sourceZoom: null
      };
    }
    const params = new URLSearchParams(rawHash);
    return {
      viewMode: params.get("view"),
      previewMode: params.get("preview"),
      selectedUnitId: params.get("unit"),
      reviewStatusFilter: params.get("reviewStatus"),
      reviewSourceQualityFilter: params.get("reviewQuality"),
      sourceZoom: params.get("zoom") ? clampZoom(params.get("zoom")) : null
    };
  }

  function buildHashFromState(state) {
    const params = new URLSearchParams();
    if (state.viewMode) {
      params.set("view", state.viewMode);
    }
    if (state.previewMode) {
      params.set("preview", state.previewMode);
    }
    if (state.selectedUnitId) {
      params.set("unit", state.selectedUnitId);
    }
    if (state.reviewStatusFilter && state.reviewStatusFilter !== "all") {
      params.set("reviewStatus", state.reviewStatusFilter);
    }
    if (state.reviewSourceQualityFilter && state.reviewSourceQualityFilter !== "all") {
      params.set("reviewQuality", state.reviewSourceQualityFilter);
    }
    if (state.sourceZoom && state.sourceZoom !== DEFAULT_ZOOM) {
      params.set("zoom", String(state.sourceZoom));
    }
    return `#${params.toString()}`;
  }

  function createInitialState(catalog, hashValue) {
    const units = Array.isArray(catalog && catalog.units) ? catalog.units : [];
    const parsed = parseHashState(hashValue);
    const selectedUnitId = units.some((unit) => unit.unitId === parsed.selectedUnitId)
      ? parsed.selectedUnitId
      : (units.length ? units[0].unitId : null);

    return {
      viewMode: parsed.viewMode === "rules" || parsed.viewMode === "review" || parsed.viewMode === "factions" ? parsed.viewMode : "units",
      previewMode: parsed.previewMode === "source" ? "source" : "digital",
      selectedUnitId,
      reviewStatusFilter: parsed.reviewStatusFilter || "all",
      reviewSourceQualityFilter: parsed.reviewSourceQualityFilter || "all",
      sourceZoom: parsed.sourceZoom || DEFAULT_ZOOM
    };
  }

  function getVisibleUnits(state, catalog) {
    const units = Array.isArray(catalog && catalog.units) ? catalog.units : [];
    if (state.viewMode !== "review") {
      return units;
    }

    return units.filter((unit) => {
      const verification = unit.verification || {};
      const statusMatch = state.reviewStatusFilter === "all" || verification.status === state.reviewStatusFilter;
      const qualityMatch = state.reviewSourceQualityFilter === "all" || verification.sourceQuality === state.reviewSourceQualityFilter;
      return statusMatch && qualityMatch;
    });
  }

  function getSelectedUnit(state, catalog) {
    const visibleUnits = getVisibleUnits(state, catalog);
    const units = visibleUnits.length ? visibleUnits : (Array.isArray(catalog && catalog.units) ? catalog.units : []);
    return units.find((unit) => unit.unitId === state.selectedUnitId) || units[0] || null;
  }

  function ensureSelectedUnitVisible(state, catalog) {
    const current = Object.assign({}, state);
    const selected = getSelectedUnit(current, catalog);
    current.selectedUnitId = selected ? selected.unitId : null;
    return current;
  }

  function reduceState(state, action, catalog) {
    const current = Object.assign({}, state);
    const visibleUnits = getVisibleUnits(current, catalog);
    if (!action || !action.type) {
      return current;
    }

    if (action.type === "set-view-mode") {
      current.viewMode = action.value === "rules" || action.value === "review" || action.value === "factions" ? action.value : "units";
      return ensureSelectedUnitVisible(current, catalog);
    }

    if (action.type === "set-preview-mode") {
      current.previewMode = action.value === "source" ? "source" : "digital";
      return current;
    }

    if (action.type === "select-unit") {
      const nextId = String(action.value || "");
      const allUnits = Array.isArray(catalog && catalog.units) ? catalog.units : [];
      current.selectedUnitId = allUnits.some((unit) => unit.unitId === nextId)
        ? nextId
        : current.selectedUnitId;
      return ensureSelectedUnitVisible(current, catalog);
    }

    if (action.type === "set-review-status-filter") {
      current.reviewStatusFilter = action.value || "all";
      return ensureSelectedUnitVisible(current, catalog);
    }

    if (action.type === "set-review-source-quality-filter") {
      current.reviewSourceQualityFilter = action.value || "all";
      return ensureSelectedUnitVisible(current, catalog);
    }

    if (action.type === "adjust-source-zoom") {
      current.sourceZoom = clampZoom((current.sourceZoom || DEFAULT_ZOOM) + Number(action.value || 0));
      return current;
    }

    if (action.type === "reset-source-zoom") {
      current.sourceZoom = DEFAULT_ZOOM;
      return current;
    }

    if (action.type === "select-relative-unit") {
      if (!visibleUnits.length) {
        return current;
      }
      const selected = getSelectedUnit(current, catalog);
      const currentIndex = Math.max(0, visibleUnits.findIndex((unit) => selected && unit.unitId === selected.unitId));
      const delta = Number(action.value || 0);
      const nextIndex = Math.max(0, Math.min(visibleUnits.length - 1, currentIndex + delta));
      current.selectedUnitId = visibleUnits[nextIndex].unitId;
      return current;
    }

    if (action.type === "scroll-to-section") {
      return current;
    }

    return current;
  }

  function syncHash(state) {
    if (typeof window === "undefined" || !window.history || typeof window.history.replaceState !== "function") {
      return;
    }
    window.history.replaceState(null, "", buildHashFromState(state));
  }

  function renderViewToggle(state) {
    return `
      <div class="toggle-row">
        <button class="toggle-btn ${state.viewMode === "units" ? "is-active" : ""}" data-action="set-view-mode" data-value="units">Units</button>
        <button class="toggle-btn ${state.viewMode === "rules" ? "is-active" : ""}" data-action="set-view-mode" data-value="rules">Rules</button>
        <button class="toggle-btn ${state.viewMode === "factions" ? "is-active" : ""}" data-action="set-view-mode" data-value="factions">Factions</button>
        <button class="toggle-btn ${state.viewMode === "review" ? "is-active" : ""}" data-action="set-view-mode" data-value="review">Review</button>
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

  function renderFilterButtons(actionName, activeValue, options) {
    return `
      <div class="toggle-row toggle-row-tight">
        ${options.map((option) => `
          <button
            class="toggle-btn toggle-btn-small ${activeValue === option.value ? "is-active" : ""}"
            data-action="${escapeHtml(actionName)}"
            data-value="${escapeHtml(option.value)}"
          >${escapeHtml(option.label)}</button>
        `).join("")}
      </div>
    `;
  }

  function summarizeUnit(unit) {
    const verification = unit && unit.verification ? unit.verification : null;
    const pointLabel = unit && unit.points != null ? `${unit.points} pts` : "? pts";
    const maxLabel = unit && unit.maxPerSquad != null ? `Max ${unit.maxPerSquad}` : null;
    return `
      <button class="unit-button" data-action="select-unit" data-value="${escapeHtml(unit.unitId)}">
        <span class="unit-name">${escapeHtml(unit.name)}</span>
        <span class="unit-meta">${escapeHtml(pointLabel)}${maxLabel ? ` · ${escapeHtml(maxLabel)}` : ""}</span>
        <div class="pill-row">
          ${renderer.renderTrustBadge(verification, "pill-inline")}
          ${unit.tags.map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("")}
        </div>
      </button>
    `;
  }

  function renderSidebar(state, manifest, catalog) {
    const rules = Array.isArray(catalog && catalog.rules) ? catalog.rules : [];
    const factions = Array.isArray(catalog && catalog.factions) ? catalog.factions : [];
    const visibleUnits = getVisibleUnits(state, catalog);
    const selected = getSelectedUnit(state, catalog);
    const summary = manifest && manifest.verificationSummary ? manifest.verificationSummary : {};
    const unitButtons = visibleUnits.map((unit) => {
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
          <p>${escapeHtml((manifest && manifest.unitCount) || visibleUnits.length)} unit cards. ${(manifest && manifest.rulesSectionCount) || 0} rule sections. ${(manifest && manifest.factionCount) || 0} factions.</p>
        </div>
        ${renderViewToggle(state)}
        ${state.viewMode === "rules" ? `
          <section class="sidebar-panel">
            <span class="section-label">Rule Groups</span>
            <div class="rule-list">
              ${rules.map((group) => `
                <button class="unit-button rule-anchor" data-action="scroll-to-section" data-value="${escapeHtml(group.id)}">
                  <span class="unit-name">${escapeHtml(group.title)}</span>
                  <span class="rule-list-label">${escapeHtml(group.sections.length)} sections</span>
                </button>
              `).join("")}
            </div>
          </section>
        ` : state.viewMode === "factions" ? `
          <section class="sidebar-panel">
            <span class="section-label">Factions</span>
            <div class="rule-list">
              ${factions.map((group) => `
                <button class="unit-button rule-anchor" data-action="scroll-to-section" data-value="${escapeHtml(group.id)}">
                  <span class="unit-name">${escapeHtml(group.title)}</span>
                  <span class="rule-list-label">${escapeHtml(group.sections.length)} sections</span>
                </button>
              `).join("")}
            </div>
          </section>
        ` : `
          <section class="sidebar-panel">
            <span class="section-label">${state.viewMode === "review" ? "Review Queue" : "Units"}</span>
            ${state.viewMode === "review" ? `
              <div class="sidebar-summary">
                <div class="sidebar-summary-row"><span>Verified</span><strong>${escapeHtml(summary.fullyVerifiedCount || 0)}</strong></div>
                <div class="sidebar-summary-row"><span>In review</span><strong>${escapeHtml(summary.inReviewCount || 0)}</strong></div>
                <div class="sidebar-summary-row"><span>Unverified</span><strong>${escapeHtml(summary.unverifiedCount || 0)}</strong></div>
                <div class="sidebar-summary-row"><span>Unresolved fields</span><strong>${escapeHtml(summary.unresolvedFieldTotal || 0)}</strong></div>
              </div>
              <div class="sidebar-panel">
                <span class="section-label">Status Filter</span>
                ${renderFilterButtons("set-review-status-filter", state.reviewStatusFilter, [
                  { value: "all", label: "All" },
                  { value: "unverified", label: "Unverified" },
                  { value: "in_review", label: "In Review" },
                  { value: "verified", label: "Verified" }
                ])}
              </div>
              <div class="sidebar-panel">
                <span class="section-label">Source Quality</span>
                ${renderFilterButtons("set-review-source-quality-filter", state.reviewSourceQualityFilter, [
                  { value: "all", label: "All" },
                  { value: "poor", label: "Poor" },
                  { value: "fair", label: "Fair" },
                  { value: "good", label: "Good" }
                ])}
              </div>
            ` : ""}
            <div class="unit-list">${unitButtons || '<div class="empty-state">No cards match the current review filters.</div>'}</div>
          </section>
        `}
      </aside>
    `;
  }

  function renderSourceCard(unit, state, options) {
    if (!unit) {
      return '<div class="empty-state">No unit selected.</div>';
    }
    const zoom = clampZoom(state.sourceZoom);
    const showControls = !options || options.showControls !== false;
    return `
      <figure class="source-surface">
        <header class="source-header">
          <div>
            <span class="section-label">Source Capture</span>
            <h2 class="rules-title">${escapeHtml(unit.name)}</h2>
          </div>
          ${showControls ? `
            <div class="zoom-controls">
              <button class="toggle-btn toggle-btn-small" data-action="adjust-source-zoom" data-value="-${ZOOM_STEP}">-</button>
              <button class="toggle-btn toggle-btn-small" data-action="reset-source-zoom">100%</button>
              <button class="toggle-btn toggle-btn-small" data-action="adjust-source-zoom" data-value="${ZOOM_STEP}">+</button>
            </div>
          ` : ""}
        </header>
        <div class="source-image-scroll">
          <img
            src="${escapeHtml(unit.sourceImageUrl)}"
            alt="Source datasheet for ${escapeHtml(unit.name)}"
            class="source-image-zoomable"
            style="width:${escapeHtml(zoom * 100)}%;"
          >
        </div>
        <p class="source-copy">Rendered source page from the canonical Heaven Fall datasheet PDF. Use zoom and scroll to inspect the original published values and rules text.</p>
      </figure>
    `;
  }

  function renderChecklist(verification) {
    const checklist = verification && verification.reviewChecklist ? verification.reviewChecklist : {};
    return `
      <div class="review-checklist">
        ${["stats", "defense", "attacks", "tags", "rulesText"].map((key) => `
          <label class="check-row">
            <input type="checkbox" ${checklist[key] ? "checked" : ""} disabled>
            <span>${escapeHtml(key)}</span>
          </label>
        `).join("")}
      </div>
    `;
  }

  function renderFieldNoteRows(fieldNotes, unresolvedFields) {
    const keys = unresolvedFields && unresolvedFields.length ? unresolvedFields : Object.keys(fieldNotes || {});
    if (!keys.length) {
      return '<div class="empty-state">No unresolved field notes on this card.</div>';
    }
    return `
      <div class="review-field-notes">
        ${keys.map((key) => `
          <div class="review-note-row">
            <div class="review-note-key">${escapeHtml(key)}</div>
            <div class="review-note-value">${escapeHtml((fieldNotes && fieldNotes[key]) || "No note recorded.")}</div>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderFieldSummary(title, entries, displayFields) {
    const rows = Array.isArray(entries) ? entries : [];
    if (!rows.length) {
      return "";
    }
    return `
      <section class="card-section">
        <h2 class="section-heading">${escapeHtml(title)}</h2>
        <div class="section-body">
          <div class="review-data-table">
            ${rows.map((entry, index) => `
              <div class="review-data-row">
                <div class="review-data-title">${escapeHtml(entry.label || entry.name || `${title} ${index + 1}`)}</div>
                <div class="review-data-grid">
                  ${displayFields.map((field) => `
                    <div>
                      <span class="meta-label">${escapeHtml(field.label)}</span>
                      <div>${escapeHtml(entry[field.key] === undefined || entry[field.key] === null ? "?" : String(entry[field.key]))}</div>
                    </div>
                  `).join("")}
                  ${entry.sourceText ? `
                    <div class="review-source-text">
                      <span class="meta-label">Source Text</span>
                      <div>${escapeHtml(entry.sourceText)}</div>
                    </div>
                  ` : ""}
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      </section>
    `;
  }

  function renderReviewPanel(unit) {
    if (!unit) {
      return '<div class="empty-state">No unit selected.</div>';
    }
    const verification = unit.verification || {};
    return `
      <section class="rules-surface">
        <header class="rules-group-header">
          <div>
            <span class="section-label">Maintainer Review</span>
            <h2 class="rules-title">${escapeHtml(unit.name)}</h2>
          </div>
          ${renderer.renderTrustBadge(verification)}
        </header>
        <div class="rule-section-body">
          <div class="review-summary-grid">
            <div>
              <span class="meta-label">Points</span>
              <div>${escapeHtml(unit.points != null ? `${unit.points} pts` : "?")}</div>
            </div>
            <div>
              <span class="meta-label">Max</span>
              <div>${escapeHtml(unit.maxPerSquad != null ? String(unit.maxPerSquad) : "-")}</div>
            </div>
            <div>
              <span class="meta-label">Status</span>
              <div>${escapeHtml(renderer.verificationLabel(verification))}</div>
            </div>
            <div>
              <span class="meta-label">Source Quality</span>
              <div>${escapeHtml(verification.sourceQuality || "?")}</div>
            </div>
            <div>
              <span class="meta-label">Updated</span>
              <div>${escapeHtml(verification.updatedAt || "?")}</div>
            </div>
            <div>
              <span class="meta-label">Checklist</span>
              <div>${escapeHtml((verification.progress && verification.progress.completed) || 0)}/${escapeHtml((verification.progress && verification.progress.total) || 0)} complete</div>
            </div>
          </div>
          <section class="card-section">
            <h2 class="section-heading">Review Checklist</h2>
            <div class="section-body">${renderChecklist(verification)}</div>
          </section>
          <section class="card-section">
            <h2 class="section-heading">Field Notes</h2>
            <div class="section-body">
              ${renderFieldNoteRows(verification.fieldNotes || {}, verification.unresolvedFields || [])}
            </div>
          </section>
          ${renderFieldSummary("Stats Summary", unit.stats, [{ key: "value", label: "Value" }])}
          ${renderFieldSummary("Defense Summary", unit.defense, [{ key: "value", label: "Value" }])}
          ${renderFieldSummary("Attack Summary", unit.attacks, [
            { key: "kind", label: "Kind" },
            { key: "range", label: "Range" },
            { key: "atk", label: "Atk" },
            { key: "hit", label: "Hit" },
            { key: "str", label: "Str" },
            { key: "aoe", label: "AoE" },
            { key: "dmg", label: "Dmg" }
          ])}
          ${renderer.renderNotesSection("Special Rules", unit.specialRules, "notes-list")}
          ${renderer.renderNotesSection("Unit Notes", unit.rulesText, "notes-list")}
        </div>
      </section>
    `;
  }

  function renderRulesView(catalog) {
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

  function renderFactionsView(catalog) {
    return `
      <main class="main">
        <div class="main-card">
          <header class="view-header">
            <div>
              <span class="section-label">Faction Rules</span>
              <h2 class="view-title">Faction Compendium</h2>
              <p class="view-copy">Faction-specific passives, cell abilities, and alliance rules extracted from the faction rules PDF.</p>
            </div>
          </header>
          ${renderer.renderRulesGroups(catalog.factions)}
        </div>
      </main>
    `;
  }

  function renderReviewView(state, catalog) {
    const selected = getSelectedUnit(state, catalog);
    const visibleUnits = getVisibleUnits(state, catalog);
    return `
      <main class="main">
        <div class="main-card">
          <header class="view-header">
            <div>
              <span class="section-label">Verification Workflow</span>
              <h2 class="view-title">${selected ? escapeHtml(selected.name) : "No Matching Unit"}</h2>
              <p class="view-copy">Compare the digital card against the canonical PDF source page and review any remaining verification metadata.</p>
            </div>
            <div class="toggle-row">
              <button class="toggle-btn" data-action="select-relative-unit" data-value="-1">Previous</button>
              <button class="toggle-btn" data-action="select-relative-unit" data-value="1">Next</button>
              <span class="pill">${escapeHtml(selected ? `${visibleUnits.findIndex((unit) => unit.unitId === selected.unitId) + 1}` : "0")}/${escapeHtml(visibleUnits.length)}</span>
            </div>
          </header>
          ${selected ? `
            <div class="review-compare-grid">
              <div class="review-compare-column">${renderer.renderDigitalCard(selected)}</div>
              <div class="review-compare-column">${renderSourceCard(selected, state)}</div>
            </div>
            <div class="review-detail-grid">
              ${renderReviewPanel(selected)}
            </div>
          ` : '<div class="empty-state">No cards match the current review filters.</div>'}
        </div>
      </main>
    `;
  }

  function renderUnitsView(state, catalog) {
    const selected = getSelectedUnit(state, catalog);
    return `
      <main class="main">
        <div class="main-card">
          <header class="view-header">
            <div>
              <span class="section-label">Unit Library</span>
              <h2 class="view-title">${selected ? escapeHtml(selected.name) : "No Unit Selected"}</h2>
              <p class="view-copy">Toggle between the rebuilt card and the rendered source page from the canonical datasheet PDF.</p>
            </div>
            ${renderPreviewToggle(state)}
          </header>
          ${selected ? (state.previewMode === "source"
            ? renderSourceCard(selected, state, { showControls: false })
            : renderer.renderDigitalCard(selected)) : '<div class="empty-state">No unit cards were found.</div>'}
        </div>
      </main>
    `;
  }

  function renderMain(state, catalog) {
    if (state.viewMode === "rules") {
      return renderRulesView(catalog);
    }
    if (state.viewMode === "factions") {
      return renderFactionsView(catalog);
    }
    if (state.viewMode === "review") {
      return renderReviewView(state, catalog);
    }
    return renderUnitsView(state, catalog);
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
      let state = createInitialState(catalog, typeof window !== "undefined" ? window.location.hash : "");
      state = ensureSelectedUnitVisible(state, catalog);
      renderApp(rootElement, state, manifest, catalog);
      syncHash(state);
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
        syncHash(state);
        if (target.getAttribute("data-action") === "scroll-to-section" && typeof document !== "undefined") {
          const section = document.getElementById(target.getAttribute("data-value") || "");
          if (section && typeof section.scrollIntoView === "function") {
            section.scrollIntoView({ block: "start", behavior: "smooth" });
          }
        }
      });
      if (typeof window !== "undefined") {
        window.addEventListener("hashchange", function () {
          state = ensureSelectedUnitVisible(createInitialState(catalog, window.location.hash), catalog);
          renderApp(rootElement, state, manifest, catalog);
          syncHash(state);
        });
      }
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
    buildHashFromState,
    createInitialState,
    getSelectedUnit,
    getVisibleUnits,
    parseHashState,
    reduceState,
    renderApp
  };
});
