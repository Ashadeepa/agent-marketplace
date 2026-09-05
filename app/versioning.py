"""
Behavioral versioning.

The talk's core claim: an agent's *API contract* (the shape of requests/responses) and its
*behavior* (what it actually does with a given input) are two different axes that change
independently. Semver on the API contract alone can't tell a caller "this will act differently
now" — a prompt tweak, a model swap, a new tool, or a loosened policy can all change behavior
while leaving the contract untouched.

This module computes a `behavior_hash` from exactly the fields that affect behavior, and diffs
two manifest versions to explain *why* something is a breaking behavioral change even when
`api_contract_version` didn't move.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.models import AgentManifest


def compute_behavior_hash(m: AgentManifest) -> str:
    """Hash the behavioral surface: prompt, model, tools, policies. NOT the api contract."""
    surface = {
        "prompt_template_id": m.prompt_template_id,
        "prompt_fingerprint": m.prompt_fingerprint,
        "model": {"provider": m.model.provider, "name": m.model.name},
        "tools": sorted(
            [{"name": t.name, "permission": t.permission.value, "scope": t.scope} for t in m.tools],
            key=lambda t: t["name"],
        ),
        "policies": sorted(m.policies),
    }
    blob = json.dumps(surface, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()[:16]


@dataclass
class VersionDiff:
    from_version: str
    to_version: str
    api_contract_changed: bool
    behavior_changed: bool
    reasons: list[str] = field(default_factory=list)
    new_permissions_requested: list[str] = field(default_factory=list)

    @property
    def is_silent_breaking_change(self) -> bool:
        """The dangerous case: behavior moved, but the API contract says nothing changed —
        so callers who only watch the contract version will never notice."""
        return self.behavior_changed and not self.api_contract_changed

    @property
    def requires_reapproval(self) -> bool:
        return self.behavior_changed or bool(self.new_permissions_requested)


def diff_versions(old: AgentManifest, new: AgentManifest) -> VersionDiff:
    reasons: list[str] = []

    if old.prompt_template_id != new.prompt_template_id or old.prompt_fingerprint != new.prompt_fingerprint:
        reasons.append(f"prompt changed ({old.prompt_template_id} → {new.prompt_template_id})")
    if (old.model.provider, old.model.name) != (new.model.provider, new.model.name):
        reasons.append(f"model changed ({old.model.name} → {new.model.name})")

    old_tools = {(t.name, t.permission.value, t.scope) for t in old.tools}
    new_tools = {(t.name, t.permission.value, t.scope) for t in new.tools}
    if old_tools != new_tools:
        added = new_tools - old_tools
        removed = old_tools - new_tools
        if added:
            reasons.append(f"tools added/changed: {sorted(t[0] for t in added)}")
        if removed:
            reasons.append(f"tools removed: {sorted(t[0] for t in removed)}")

    if set(old.policies) != set(new.policies):
        reasons.append(f"policies changed ({sorted(old.policies)} → {sorted(new.policies)})")

    old_perms = old.requested_permission_levels()
    new_perms = new.requested_permission_levels()
    new_permissions_requested = sorted(new_perms - old_perms)

    behavior_changed = compute_behavior_hash(old) != compute_behavior_hash(new)
    api_contract_changed = old.api_contract_version != new.api_contract_version

    return VersionDiff(
        from_version=old.version,
        to_version=new.version,
        api_contract_changed=api_contract_changed,
        behavior_changed=behavior_changed,
        reasons=reasons,
        new_permissions_requested=new_permissions_requested,
    )
