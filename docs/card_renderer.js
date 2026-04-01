(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.HeavenFallCardRenderer = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function displayValue(value) {
    return value === null || value === undefined || value === "" ? "?" : String(value);
  }

  function verificationTone(verification) {
    if (!verification) {
      return "review";
    }
    if (verification.status === "verified") {
      return "verified";
    }
    if (verification.sourceQuality === "poor") {
      return "unclear";
    }
    return "review";
  }

  function verificationLabel(verification) {
    if (!verification) {
      return "Needs review";
    }
    return verification.statusLabel || (
      verification.status === "verified" ? "Verified" : (
        verification.sourceQuality === "poor" ? "Source unclear" : "Needs review"
      )
    );
  }

  function renderTrustBadge(verification, extraClass) {
    return `<span class="pill verification-badge verification-badge-${escapeHtml(verificationTone(verification))} ${escapeHtml(extraClass || "")}">${escapeHtml(verificationLabel(verification))}</span>`;
  }

  function renderStatGrid(stats) {
    if (!Array.isArray(stats) || !stats.length) {
      return "";
    }
    return `
      <section class="card-section">
        <h2 class="section-heading">Stats</h2>
        <div class="section-body">
          <div class="chip-grid">
            ${stats.map((stat) => `
              <div class="stat-chip">
                <span class="chip-label">${escapeHtml(stat.label)}</span>
                <span class="chip-value">${escapeHtml(displayValue(stat.value))}</span>
              </div>
            `).join("")}
          </div>
        </div>
      </section>
    `;
  }

  function renderDefenseGrid(defense) {
    if (!Array.isArray(defense) || !defense.length) {
      return "";
    }
    return `
      <section class="card-section">
        <h2 class="section-heading">Defense</h2>
        <div class="section-body">
          <div class="defense-grid">
            ${defense.map((item) => `
              <div class="defense-chip">
                <span class="chip-label">${escapeHtml(item.label)}</span>
                <span class="chip-value">${escapeHtml(displayValue(item.value))}</span>
              </div>
            `).join("")}
          </div>
        </div>
      </section>
    `;
  }

  function renderAttackNotes(notes) {
    const items = Array.isArray(notes) ? notes.filter(Boolean) : [];
    if (!items.length) {
      return "";
    }
    return `<ul class="attack-notes">${items.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>`;
  }

  function renderAttacks(attacks) {
    if (!Array.isArray(attacks) || !attacks.length) {
      return "";
    }
    return `
      <section class="card-section">
        <h2 class="section-heading">Attacks</h2>
        <div class="section-body">
          <table class="attack-table">
            <thead>
              <tr>
                <th>Attack</th>
                <th>Kind</th>
                <th>Range</th>
                <th>Atk</th>
                <th>Hit</th>
                <th>Str</th>
                <th>AoE</th>
                <th>Dmg</th>
              </tr>
            </thead>
            <tbody>
              ${attacks.map((attack) => `
                <tr>
                  <td>
                    <div class="attack-name">${escapeHtml(attack.name)}</div>
                    ${renderAttackNotes(attack.notes)}
                  </td>
                  <td>${escapeHtml(displayValue(attack.kind))}</td>
                  <td>${escapeHtml(displayValue(attack.range))}</td>
                  <td>${escapeHtml(displayValue(attack.atk))}</td>
                  <td>${escapeHtml(displayValue(attack.hit))}</td>
                  <td>${escapeHtml(displayValue(attack.str))}</td>
                  <td>${escapeHtml(displayValue(attack.aoe))}</td>
                  <td>${escapeHtml(displayValue(attack.dmg))}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </section>
    `;
  }

  function renderTagSection(tags) {
    const items = Array.isArray(tags) ? tags.filter(Boolean) : [];
    if (!items.length) {
      return "";
    }
    return `
      <section class="card-section">
        <h2 class="section-heading">Tags</h2>
        <div class="section-body">
          <div class="pill-row">
            ${items.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}
          </div>
        </div>
      </section>
    `;
  }

  function renderNotesSection(title, values, className) {
    const items = Array.isArray(values) ? values.filter(Boolean) : [];
    if (!items.length) {
      return "";
    }
    return `
      <section class="card-section">
        <h2 class="section-heading">${escapeHtml(title)}</h2>
        <div class="section-body">
          <ul class="${escapeHtml(className || "notes-list")}">
            ${items.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}
          </ul>
        </div>
      </section>
    `;
  }

  function renderVerificationPanel(unit) {
    const verification = unit && unit.verification ? unit.verification : null;
    if (!verification) {
      return "";
    }
    return `
      <aside class="verification-panel verification-panel-${escapeHtml(verificationTone(verification))}">
        <div class="verification-panel-header">
          <h3>${escapeHtml(verificationLabel(verification))}</h3>
          ${renderTrustBadge(verification)}
        </div>
        <p>Capture quality: <strong>${escapeHtml(displayValue(verification.sourceQuality))}</strong>. Reviewed: <strong>${escapeHtml(displayValue(verification.updatedAt))}</strong>.</p>
        ${verification.hasUnresolvedFields ? `
          ${renderNotesSection("Unresolved Fields", verification.unresolvedFields, "notes-list")}
          ${renderNotesSection("Capture Notes", verification.notes, "notes-list")}
        ` : "<p>No unresolved fields remain on this card.</p>"}
      </aside>
    `;
  }

  function renderDigitalCard(unit) {
    const tags = Array.isArray(unit && unit.tags) ? unit.tags : [];
    const verification = unit && unit.verification ? unit.verification : {};
    const maxLabel = unit && unit.maxPerSquad != null ? `Max ${unit.maxPerSquad}` : "Max ?";
    return `
      <article class="card-surface">
        <header class="card-header">
          <div>
            <span class="section-label">Heaven Fall Unit</span>
            <h1 class="card-title">${escapeHtml(unit.name)}</h1>
            <div class="pill-row">
              <span class="pill">${escapeHtml(maxLabel)}</span>
              ${renderTrustBadge(verification)}
              ${tags.map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("")}
            </div>
          </div>
          <div class="card-meta">
            <span class="meta-label">Card Id</span>
            <div>${escapeHtml(unit.unitId)}</div>
          </div>
        </header>
        ${renderVerificationPanel(unit)}
        <div class="card-grid">
          <div class="card-column">
            ${renderStatGrid(unit.stats)}
            ${renderDefenseGrid(unit.defense)}
            ${renderTagSection(unit.tags)}
          </div>
          <div class="card-column">
            ${renderAttacks(unit.attacks)}
            ${renderNotesSection("Unit Notes", unit.rulesText, "notes-list")}
          </div>
        </div>
      </article>
    `;
  }

  function renderRulesGroups(groups) {
    const ruleGroups = Array.isArray(groups) ? groups : [];
    if (!ruleGroups.length) {
      return '<div class="empty-state">No rules were found in the catalog.</div>';
    }
    return ruleGroups.map((group) => `
      <section class="rules-group rules-surface" id="${escapeHtml(group.id)}">
        <header class="rules-group-header">
          <span class="section-label">Rule Group</span>
          <h2 class="rules-title">${escapeHtml(group.title)}</h2>
        </header>
        ${group.sections.map((section) => `
          <article class="rule-section" id="rule-${escapeHtml(section.id)}">
            <div class="section-heading">${escapeHtml(section.title)}</div>
            <div class="rule-section-body">
              ${(section.body || []).map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}
            </div>
          </article>
        `).join("")}
      </section>
    `).join("");
  }

  return {
    escapeHtml,
    renderDigitalCard,
    renderRulesGroups,
    verificationLabel,
    verificationTone,
    renderTrustBadge
  };
});
