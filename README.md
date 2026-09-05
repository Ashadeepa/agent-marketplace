# Agent Marketplace — Sample Project

![Agents in registry](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ashadeepa/agent-marketplace/main/badges/agents-count.json)

A small, runnable prototype of an **internal marketplace for AI agents**, built to accompany the talk
*"The App Store for AI Agents: Building Discovery, Trust & Versioning at Scale."*

It is deliberately minimal (no external services, no API keys, no ML downloads) so it runs anywhere in
under a minute, while still making the five hard problems from the talk concrete and inspectable:

| Pillar | Where it lives |
|---|---|
| **Discovery** — capability search, not keyword match | `app/search.py` |
| **Capability manifests** — explicit tools/permissions/deps before install | `data/agents/*.json`, `app/models.py` |
| **Behavioral versioning** — same contract, different behavior | `app/versioning.py` |
| **Trust & governance** — publisher identity, review, evals, approval gates | `app/governance.py` |
| **Tenant-scoped visibility** — who can even see an agent | `app/tenancy.py` |
| **Invocation tracing** (optional) — a record of what actually ran, not just the manifest | `app/tracing.py` |
| **MCP server** (optional) — the marketplace itself, reachable as tools from Claude | `mcp_server.py` |

## Quick start

```bash
cd agent-marketplace
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed.py          # loads data/agents/*.json into the in-memory registry (no-op, just validates)
uvicorn app.main:app --reload   # http://localhost:8000
```

Open `http://localhost:8000` for the browsable marketplace UI, or hit the API directly:

```bash
# Discover agents by capability, scoped to a tenant
curl "http://localhost:8000/agents?q=reconcile+invoices&tenant_id=finance"

# Inspect the full capability manifest (permissions, tools, policies, review status)
curl "http://localhost:8000/agents/billing-reconciler"

# See behavioral version history — including where behavior changed under an unchanged API contract
curl "http://localhost:8000/agents/billing-reconciler/versions"

# Try to install an agent that requests elevated permissions but isn't approved yet
curl -X POST "http://localhost:8000/agents/support-triage/install?tenant_id=support"
```

## Run the tests

```bash
pytest tests/ -v
```

The tests double as a spec for the two trickiest pieces: what counts as a *breaking behavioral change*,
and how tenant visibility + approval gates combine to decide whether an install is allowed.

## Optional: trace invocations to LangSmith

The `/agents/{id}/invoke` and `/agents/{id}/install` endpoints are wrapped with a `@traceable`
decorator (`app/tracing.py`). With no configuration this is a no-op — the app behaves exactly as
above. To send those calls to [LangSmith](https://smith.langchain.com) as traces instead:

```bash
pip install -r requirements-tracing.txt
export LANGCHAIN_API_KEY=ls__...              # from smith.langchain.com → Settings → API Keys
export LANGCHAIN_PROJECT=agent-marketplace-sample   # optional, this is the default
uvicorn app.main:app --reload
```

Then call the API as usual (or click around the UI) and each install/invoke shows up as a run in
your LangSmith project, tagged with `agent_id`, `version`, and `tenant_id`. Check whether tracing
picked up your key without leaving the terminal:

```bash
curl "http://localhost:8000/admin/tracing-status"
# {"langsmith_tracing_enabled": true, "reason": "enabled", "project": "agent-marketplace-sample"}
```

If `langsmith` isn't installed, or no API key is set, this endpoint tells you why tracing is off —
the rest of the app is unaffected either way.

## Optional: run it as an MCP server for Claude

`mcp_server.py` exposes the same marketplace (search, manifest lookup, version history, install)
as MCP tools, so Claude itself can browse and install from it — a nice full-circle demo, since the
talk is about agents discovering and installing other agents.

```bash
pip install -r requirements-mcp.txt
```

**Claude Code:**

```bash
claude mcp add agent-marketplace -- python /absolute/path/to/agent-marketplace/mcp_server.py
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-marketplace": {
      "command": "python",
      "args": ["/absolute/path/to/agent-marketplace/mcp_server.py"]
    }
  }
}
```

Restart Claude, then try prompts like:

- "Search the agent marketplace for something that reconciles invoices, for the finance tenant."
- "Show me the version history for billing-reconciler — did any version change behavior silently?"
- "Try installing support-triage for the support tenant. If it's blocked, tell me why."

This runs in-process against the same `app/registry.py`, `app/search.py`, `app/governance.py`,
`app/tenancy.py`, and `app/versioning.py` modules the FastAPI app uses — it's a second front door
on the same marketplace, not a separate implementation, so anything you change in `data/agents/`
shows up identically through the API, the browser UI, and Claude.

## What's deliberately simplified (and how to extend it)

This is a talk companion, not a production system. The obvious next steps if you wanted to take it further:

- **Discovery**: `app/search.py` uses a small hand-rolled TF-IDF + capability-tag boost so the demo has
  zero external dependencies. Swap `score_agents()` for real embeddings (e.g. an embedding model over
  `name + description + capabilities`) and an ANN index (pgvector, FAISS) once you have enough agents
  that lexical overlap stops being good enough.
- **Storage**: the registry is in-memory, seeded from JSON files on disk. A real system needs a durable
  store (manifests + version history), plus an audit log of every install/invoke decision — governance
  without an audit trail isn't governance.
- **Behavioral versioning**: `behavior_hash` here is a SHA-256 over `(prompt_template, model, tools,
  policies)`. In production you'd likely add eval-result deltas and a human-in-the-loop diff view, since
  a changed hash tells you *that* behavior may have changed, not *how much it matters*.
- **Trust & governance**: publisher verification and eval scores are static fields on the manifest here.
  A real marketplace would re-run evals on every version bump and block promotion to `approved` on
  regression, not just take the publisher's word for it.
- **Tenant scoping**: visibility is a simple allowlist/denylist/public enum per manifest. At scale this
  usually becomes a policy engine (OPA/Cedar-style) so visibility rules can reference org hierarchy,
  data residency, and license tier instead of being hand-maintained lists.
