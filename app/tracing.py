"""
Optional LangSmith tracing for agent invocations.

Ties into the talk's "trust & governance" pillar: once agents are running in production, you want
a record of what actually ran — which version, for which tenant, with what inputs/outputs — not
just the static manifest. LangSmith is used here purely as a tracing backend for that record.

Degrades gracefully: if the `langsmith` package isn't installed, or no API key is configured, the
`@traceable` decorator below becomes a no-op and the app runs exactly as before. Nothing else in
the project depends on LangSmith being present.

To enable it:
    pip install langsmith
    export LANGCHAIN_API_KEY=ls__...          # from smith.langchain.com
    export LANGCHAIN_PROJECT=agent-marketplace-sample   # optional, defaults below

Then hit /agents/{id}/invoke or /agents/{id}/install — each call becomes a run visible in your
LangSmith project, tagged with agent_id, version, and tenant_id.
"""
from __future__ import annotations

import os
from typing import Any, Callable

_langsmith_import_error: str | None = None
try:
    from langsmith import traceable as _ls_traceable
except ImportError as e:  # pragma: no cover - exercised only when langsmith isn't installed
    _ls_traceable = None
    _langsmith_import_error = str(e)

_has_api_key = bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))
TRACING_ENABLED = _ls_traceable is not None and _has_api_key

if TRACING_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "agent-marketplace-sample"))


def traceable(name: str, run_type: str = "chain", **ls_kwargs: Any) -> Callable:
    """Thin wrapper around langsmith.traceable that no-ops when tracing isn't configured."""
    def decorator(fn: Callable) -> Callable:
        if TRACING_ENABLED:
            return _ls_traceable(name=name, run_type=run_type, **ls_kwargs)(fn)
        return fn
    return decorator


def tracing_status() -> dict:
    if TRACING_ENABLED:
        reason = "enabled"
    elif _ls_traceable is None:
        reason = "langsmith package not installed"
    else:
        reason = "LANGCHAIN_API_KEY / LANGSMITH_API_KEY not set"
    return {
        "langsmith_tracing_enabled": TRACING_ENABLED,
        "reason": reason,
        "project": os.environ.get("LANGCHAIN_PROJECT") if TRACING_ENABLED else None,
    }
