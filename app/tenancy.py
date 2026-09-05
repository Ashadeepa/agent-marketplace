"""
Tenant-scoped visibility.

Whether an agent can even be *seen* by a tenant, independent of whether installing it would be
governance-approved. A publisher might make an agent visible only to their own team while it's
being iterated on (`private`), roll it out to a handful of partner teams (`allowlist`), block a
couple of teams from an otherwise-public agent (`denylist`), or make it fully discoverable
(`public`).
"""
from __future__ import annotations

from app.models import AgentManifest, VisibilityMode


def is_visible_to_tenant(manifest: AgentManifest, tenant_id: str | None) -> bool:
    vis = manifest.tenant_visibility

    # The publisher's own tenant can always see their own agent.
    if tenant_id and tenant_id == manifest.publisher.team:
        return True

    if vis.mode == VisibilityMode.PUBLIC:
        return True
    if vis.mode == VisibilityMode.PRIVATE:
        return False
    if vis.mode == VisibilityMode.ALLOWLIST:
        return tenant_id is not None and tenant_id in vis.tenants
    if vis.mode == VisibilityMode.DENYLIST:
        return tenant_id is None or tenant_id not in vis.tenants
    return False
