from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.governance import evaluate_install, trust_badges
from app.registry import registry
from app.search import score_agents
from app.tenancy import is_visible_to_tenant
from app.tracing import traceable, tracing_status
from app.versioning import compute_behavior_hash, diff_versions

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Agent Marketplace (sample)", version="0.1.0")


@app.on_event("startup")
def _load_registry() -> None:
    registry.load_from_disk()


def _visible_agents(tenant_id: str | None):
    return [m for m in registry.all_latest() if is_visible_to_tenant(m, tenant_id)]


def _summarize(manifest, score: float | None = None, matched=None) -> dict:
    return {
        "agent_id": manifest.agent_id,
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "publisher": manifest.publisher.model_dump(),
        "capabilities": manifest.capabilities,
        "tags": manifest.tags,
        "review_status": manifest.review.status.value,
        "trust_badges": trust_badges(manifest),
        "requests_elevated_permissions": manifest.requests_elevated_permissions(),
        "score": score,
        "matched_capabilities": matched or [],
    }


@app.get("/agents")
def search_agents(
    q: str = Query("", description="Free-text capability query, e.g. 'reconcile invoices'"),
    tenant_id: str | None = Query(None, description="Requesting tenant, for visibility scoping"),
):
    """Discovery endpoint: capability search, scoped to what this tenant is allowed to see."""
    candidates = _visible_agents(tenant_id)
    hits = score_agents(q, candidates)
    return {
        "tenant_id": tenant_id,
        "query": q,
        "count": len(hits),
        "results": [_summarize(h.manifest, h.score, h.matched_capabilities) for h in hits],
    }


@app.get("/agents/{agent_id}")
def get_manifest(
    agent_id: str,
    version: str | None = Query(None, description="Specific version; defaults to latest"),
    tenant_id: str | None = Query(None),
):
    """Full capability manifest — tools, permissions, dependencies, policies, review status."""
    manifest = registry.get_version(agent_id, version) if version else registry.get_latest(agent_id)
    if manifest is None:
        raise HTTPException(404, f"agent '{agent_id}' (version={version}) not found")
    if not is_visible_to_tenant(manifest, tenant_id):
        raise HTTPException(404, f"agent '{agent_id}' not visible to tenant '{tenant_id}'")

    data = manifest.model_dump()
    data["behavior_hash"] = compute_behavior_hash(manifest)
    data["trust_badges"] = trust_badges(manifest)
    return data


@app.get("/agents/{agent_id}/versions")
def version_history(agent_id: str, tenant_id: str | None = Query(None)):
    """Behavioral version history, with a diff against the previous version for each entry."""
    versions = registry.get_all_versions(agent_id)
    if not versions:
        raise HTTPException(404, f"agent '{agent_id}' not found")
    if not is_visible_to_tenant(versions[-1], tenant_id):
        raise HTTPException(404, f"agent '{agent_id}' not visible to tenant '{tenant_id}'")

    history = []
    for i, m in enumerate(versions):
        entry = {
            "version": m.version,
            "api_contract_version": m.api_contract_version,
            "behavior_hash": compute_behavior_hash(m),
            "review_status": m.review.status.value,
            "changelog": m.changelog,
        }
        if i > 0:
            d = diff_versions(versions[i - 1], m)
            entry["diff_from_previous"] = {
                "from_version": d.from_version,
                "to_version": d.to_version,
                "api_contract_changed": d.api_contract_changed,
                "behavior_changed": d.behavior_changed,
                "is_silent_breaking_change": d.is_silent_breaking_change,
                "requires_reapproval": d.requires_reapproval,
                "new_permissions_requested": d.new_permissions_requested,
                "reasons": d.reasons,
            }
        history.append(entry)
    return {"agent_id": agent_id, "versions": history}


@app.post("/agents/{agent_id}/install")
def install_agent(
    agent_id: str,
    tenant_id: str | None = Query(None),
    version: str | None = Query(None),
):
    """Governance gate: visibility + review status + permission level all have to line up."""
    manifest = registry.get_version(agent_id, version) if version else registry.get_latest(agent_id)
    if manifest is None:
        raise HTTPException(404, f"agent '{agent_id}' (version={version}) not found")
    if not is_visible_to_tenant(manifest, tenant_id):
        raise HTTPException(404, f"agent '{agent_id}' not visible to tenant '{tenant_id}'")

    decision = evaluate_install(manifest)
    result = _traced_install(
        agent_id=agent_id,
        version=manifest.version,
        tenant_id=tenant_id,
        allowed=decision.allowed,
        reason=decision.reason,
    )
    if not decision.allowed:
        raise HTTPException(403, decision.reason)
    return result


@traceable(name="agent_install", run_type="chain")
def _traced_install(agent_id: str, version: str, tenant_id: str | None, allowed: bool, reason: str) -> dict:
    """Isolated from the FastAPI route so LangSmith traces plain, serializable inputs/outputs
    (not Query() parameter objects) — this is the function whose calls show up as runs."""
    return {
        "agent_id": agent_id,
        "version": version,
        "tenant_id": tenant_id,
        "status": "installed" if allowed else "denied",
        "reason": reason,
    }


@app.post("/agents/{agent_id}/invoke")
def invoke_agent(agent_id: str, tenant_id: str | None = Query(None)):
    """Simulated invocation — in this sample it just re-checks the same governance gate as
    install and echoes back what *would* run, since there's no real model call here."""
    manifest = registry.get_latest(agent_id)
    if manifest is None:
        raise HTTPException(404, f"agent '{agent_id}' not found")
    if not is_visible_to_tenant(manifest, tenant_id):
        raise HTTPException(404, f"agent '{agent_id}' not visible to tenant '{tenant_id}'")

    decision = evaluate_install(manifest)
    if not decision.allowed:
        _traced_invoke(
            agent_id=agent_id,
            version=manifest.version,
            tenant_id=tenant_id,
            would_run=None,
            error=f"Cannot invoke: {decision.reason}",
        )
        raise HTTPException(403, f"Cannot invoke: {decision.reason}")

    would_run = {
        "model": manifest.model.model_dump(),
        "prompt_template_id": manifest.prompt_template_id,
        "tools_available": [t.name for t in manifest.tools],
    }
    return _traced_invoke(
        agent_id=agent_id,
        version=manifest.version,
        tenant_id=tenant_id,
        would_run=would_run,
        error=None,
    )


@traceable(name="agent_invoke", run_type="chain")
def _traced_invoke(
    agent_id: str,
    version: str,
    tenant_id: str | None,
    would_run: dict | None,
    error: str | None,
) -> dict:
    """The actual traced unit of work. Every call becomes one LangSmith run tagged with
    agent_id/version/tenant_id when tracing is enabled (see app/tracing.py); it's a plain
    Python function otherwise, so nothing about the response shape depends on LangSmith."""
    if error:
        return {"agent_id": agent_id, "version": version, "tenant_id": tenant_id, "error": error}
    return {
        "agent_id": agent_id,
        "version": version,
        "tenant_id": tenant_id,
        "would_run": would_run,
        "note": "Simulated — this sample project does not call a real model.",
    }


@app.get("/admin/tracing-status")
def get_tracing_status():
    """Whether this run is exporting traces to LangSmith, and why/why not — useful for checking
    the integration without needing to open the LangSmith UI."""
    return tracing_status()


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
