const resultsEl = document.getElementById("results");
const queryEl = document.getElementById("query");
const tenantEl = document.getElementById("tenant");
const modal = document.getElementById("modal");
const modalBody = document.getElementById("modalBody");
document.getElementById("closeModal").onclick = () => modal.classList.add("hidden");
modal.addEventListener("click", (e) => { if (e.target === modal) modal.classList.add("hidden"); });

let debounceTimer;
queryEl.addEventListener("input", () => { clearTimeout(debounceTimer); debounceTimer = setTimeout(runSearch, 200); });
tenantEl.addEventListener("change", runSearch);

function badgeClass(b) {
  if (b.toLowerCase().includes("approved")) return "approved";
  if (b.toLowerCase().includes("pending")) return "pending";
  if (b.toLowerCase().includes("elevated")) return "elevated";
  if (b.toLowerCase().includes("verified")) return "verified";
  return "";
}

async function runSearch() {
  const q = encodeURIComponent(queryEl.value);
  const tenant = tenantEl.value;
  const url = `/agents?q=${q}` + (tenant ? `&tenant_id=${tenant}` : "");
  const res = await fetch(url);
  const data = await res.json();
  renderResults(data.results);
}

function renderResults(results) {
  resultsEl.innerHTML = "";
  if (results.length === 0) {
    resultsEl.innerHTML = `<div class="empty">No agents visible to this tenant match that query.</div>`;
    return;
  }
  for (const agent of results) {
    const card = document.createElement("div");
    card.className = "card";
    card.onclick = () => openAgent(agent.agent_id);
    card.innerHTML = `
      <h3>${agent.name}</h3>
      <div class="meta">${agent.agent_id} · v${agent.version} · ${agent.publisher.team}</div>
      <p>${agent.description}</p>
      <div class="badges">
        ${agent.trust_badges.map(b => `<span class="badge ${badgeClass(b)}">${b}</span>`).join("")}
      </div>
    `;
    resultsEl.appendChild(card);
  }
}

async function openAgent(agentId) {
  const tenant = tenantEl.value;
  const suffix = tenant ? `?tenant_id=${tenant}` : "";
  const [manifestRes, versionsRes] = await Promise.all([
    fetch(`/agents/${agentId}${suffix}`),
    fetch(`/agents/${agentId}/versions${suffix}`),
  ]);
  const manifest = await manifestRes.json();
  const versions = await versionsRes.json();

  modalBody.innerHTML = `
    <h2>${manifest.name} <small style="color:var(--muted)">v${manifest.version}</small></h2>
    <div>${manifest.trust_badges.map(b => `<span class="badge ${badgeClass(b)}">${b}</span>`).join(" ")}</div>
    <p>${manifest.description}</p>

    <div class="section-title">Publisher</div>
    <div>${manifest.publisher.name} · ${manifest.publisher.team} · ${manifest.publisher.verified ? "verified" : "unverified"}</div>

    <div class="section-title">Capability manifest</div>
    <pre>${JSON.stringify({
      capabilities: manifest.capabilities,
      tools: manifest.tools,
      policies: manifest.policies,
      dependencies: manifest.dependencies,
      tenant_visibility: manifest.tenant_visibility,
      behavior_hash: manifest.behavior_hash,
      review: manifest.review
    }, null, 2)}</pre>

    <div class="section-title">Behavioral version history</div>
    ${versions.versions.map(v => `
      <div class="diff-line ${v.diff_from_previous && v.diff_from_previous.is_silent_breaking_change ? "silent" : ""}">
        <strong>v${v.version}</strong> — ${v.review_status} — behavior_hash ${v.behavior_hash}
        ${v.diff_from_previous ? `
          <div style="margin-left:12px; color:var(--muted)">
            api_contract_changed: ${v.diff_from_previous.api_contract_changed},
            behavior_changed: ${v.diff_from_previous.behavior_changed}
            ${v.diff_from_previous.is_silent_breaking_change ? " — ⚠ silent breaking change (contract same, behavior changed)" : ""}
            ${v.diff_from_previous.reasons.length ? `<br/>reasons: ${v.diff_from_previous.reasons.join("; ")}` : ""}
          </div>` : ""}
      </div>
    `).join("")}

    <div class="install-row">
      <button class="action" id="installBtn">Try install (v${manifest.version})</button>
      <span style="color:var(--muted); font-size:13px;">tenant: ${tenant || "(none)"}</span>
    </div>
    <div id="installResult"></div>
  `;

  document.getElementById("installBtn").onclick = async () => {
    const r = await fetch(`/agents/${agentId}/install${suffix}`, { method: "POST" });
    const body = await r.json();
    const el = document.getElementById("installResult");
    if (r.ok) {
      el.className = "result-msg ok";
      el.textContent = `✓ ${body.reason} (installed for tenant "${body.tenant_id || "none"}")`;
    } else {
      el.className = "result-msg err";
      el.textContent = `✗ ${body.detail}`;
    }
  };

  modal.classList.remove("hidden");
}

runSearch();
