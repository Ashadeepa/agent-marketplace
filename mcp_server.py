"""
Expose the agent marketplace itself as an MCP server, so Claude (Claude Code, Claude Desktop,
or any other MCP client) can discover, inspect, and install agents from it directly — the same
five pillars from the talk, but reached as tools instead of HTTP calls.

This runs in-process against the same registry/search/governance/tenancy modules the FastAPI app
uses (app/registry.py, app/search.py, app/governance.py, app/tenancy.py, app/versioning.py) —
it's a second front door onto the same marketplace, not a separate implementation.

Run standalone for a quick check:
    python mcp_server.py

Wire it into Claude Code:
    claude mcp add agent-marketplace -- python /absolute/path/to/agent-marketplace/mcp_server.py

Or add it to Claude Desktop's config (claude_desktop_config.json):
    {
      "mcpServers": {
        "agent-marketplace": {
          "command": "python",
          "args": ["/absolute/path/to/agent-marketplace/mcp_server.py"]
        }
      }
    }

Then ask Claude things like "search the agent marketplace for something that reconciles
invoices" or "install billing-reconciler for the finance tenant" and it will call these tools.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.governance import evaluate_install, trust_badges
from app.registry import registry
from app.search import score_agents
from app.tenancy import is_visible_to_tenant
from app.versioning import compute_behavior_hash, diff_versions

mcp = FastMCP("agent-marketplace")


def _visible(tenant_id: str | None):
    return [m for m in registry.all_latest() if is_visible_to_tenant(m, tenant_id)]


def _summary(manifest, score: float | None = None, matched=None) -> dict:
    return {
        "agent_id": manifest.agent_id,
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "publisher": manifest.publisher.model_dump(),
        "capabilities": manifest.capabilities,
        "review_status": manifest.review.status.value,
        "trust_badges": trust_badges(manifest),
        "requests_elevated_permissions": manifest.requests_elevated_permissions(),
        "score": score,
        "matched_capabilities": matched or [],
    }


@mcp.tool()
def search_agents(query: str = "", tenant_id: str | None = None) -> dict:
    """Discover agents in the marketplace by capability (not just keyword match), scoped to
    what the given tenant is allowed to see. Leave query empty to list everything visible.
    tenant_id examples in this sample data: finance, support, platform, sre."""
    registry.load_from_disk()
    candidates = _visible(tenant_id)
    hits = score_agents(query, candidates)
    return {
        "tenant_id": tenant_id,
        "query": query,
        "count": len(hits),
        "results": [_summary(h.manifest, h.score, h.matched_capabilities) for h in hits],
    }


@mcp.tool()
def get_agent_manifest(agent_id: str, version: str | None = None, tenant_id: str | None = None) -> dict:
    """Fetch an agent's full capability manifest: tools, permission scopes, policies,
    dependencies, and review/trust status. Defaults to the latest version if none is given."""
    registry.load_from_disk()
    manifest = registry.get_version(agent_id, version) if version else registry.get_latest(agent_id)
    if manifest is None:
        return {"error": f"agent '{agent_id}' (version={version}) not found"}
    if not is_visible_to_tenant(manifest, tenant_id):
        return {"error": f"agent '{agent_id}' not visible to tenant '{tenant_id}'"}

    data = manifest.model_dump()
    data["behavior_hash"] = compute_behavior_hash(manifest)
    data["trust_badges"] = trust_badges(manifest)
    return data


@mcp.tool()
def get_version_history(agent_id: str, tenant_id: str | None = None) -> dict:
    """List every published version of an agent with a behavioral diff against the previous
    version — flags cases where behavior changed even though the API contract didn't
    (a 'silent breaking change'), and whether the new version needs re-approval."""
    registry.load_from_disk()
    versions = registry.get_all_versions(agent_id)
    if not versions:
        return {"error": f"agent '{agent_id}' not found"}
    if not is_visible_to_tenant(versions[-1], tenant_id):
        return {"error": f"agent '{agent_id}' not visible to tenant '{tenant_id}'"}

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
                "api_contract_changed": d.api_contract_changed,
                "behavior_changed": d.behavior_changed,
                "is_silent_breaking_change": d.is_silent_breaking_change,
                "requires_reapproval": d.requires_reapproval,
                "new_permissions_requested": d.new_permissions_requested,
                "reasons": d.reasons,
            }
        history.append(entry)
    return {"agent_id": agent_id, "versions": history}


@mcp.tool()
def install_agent(agent_id: str, tenant_id: str | None = None, version: str | None = None) -> dict:
    """Try to install an agent for a tenant. Enforces the same governance gate as the API:
    blocked if not visible to the tenant, rejected/deprecated, or requesting elevated
    permissions (write/delete/external_network) without an 'approved' review status."""
    registry.load_from_disk()
    manifest = registry.get_version(agent_id, version) if version else registry.get_latest(agent_id)
    if manifest is None:
        return {"error": f"agent '{agent_id}' (version={version}) not found"}
    if not is_visible_to_tenant(manifest, tenant_id):
        return {"error": f"agent '{agent_id}' not visible to tenant '{tenant_id}'"}

    decision = evaluate_install(manifest)
    return {
        "agent_id": agent_id,
        "version": manifest.version,
        "tenant_id": tenant_id,
        "status": "installed" if decision.allowed else "denied",
        "reason": decision.reason,
    }


if __name__ == "__main__":
    mcp.run()
