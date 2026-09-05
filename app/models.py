"""
Capability manifest schema.

The core idea from the talk: nothing about an agent should be implicit. Before an agent can be
discovered, installed, or invoked, its manifest must declare exactly what it can do, what it touches,
and who is accountable for it.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class PermissionLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXTERNAL_NETWORK = "external_network"


class VisibilityMode(str, Enum):
    PUBLIC = "public"          # discoverable by every tenant
    ALLOWLIST = "allowlist"    # only listed tenants can discover/install
    DENYLIST = "denylist"      # every tenant except the listed ones
    PRIVATE = "private"        # only the publisher's own tenant


class Publisher(BaseModel):
    name: str
    team: str
    verified: bool = False
    contact: str


class ToolBinding(BaseModel):
    """One tool the agent is allowed to call, and exactly what it's allowed to do with it."""
    name: str
    permission: PermissionLevel
    scope: str  # e.g. "finance.invoices", "#finance-alerts", "*.anthropic.com"


class EvalResults(BaseModel):
    accuracy: Optional[float] = None
    safety: Optional[str] = None  # "pass" | "fail" | "not_run"
    last_run: Optional[str] = None  # ISO date


class Review(BaseModel):
    status: ReviewStatus = ReviewStatus.DRAFT
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    evals: EvalResults = Field(default_factory=EvalResults)
    notes: Optional[str] = None


class TenantVisibility(BaseModel):
    mode: VisibilityMode = VisibilityMode.PRIVATE
    tenants: list[str] = Field(default_factory=list)  # meaning depends on `mode`


class ModelBinding(BaseModel):
    provider: str
    name: str


class AgentManifest(BaseModel):
    """
    One version of one agent. `agent_id` is stable across versions; `version` and `behavior_hash`
    are not. The API contract (inputs/outputs the agent exposes to callers) is described separately
    from the *behavioral* surface (prompt, model, tools, policies) precisely because the two can
    change independently — see app/versioning.py.
    """
    agent_id: str
    version: str  # semver
    name: str
    description: str
    publisher: Publisher

    capabilities: list[str]           # what it's *for* — drives discovery
    tags: list[str] = Field(default_factory=list)

    api_contract_version: str         # bump only when request/response shape changes
    input_schema_ref: str = "v1/generic-task"
    output_schema_ref: str = "v1/generic-result"

    model: ModelBinding
    prompt_template_id: str           # points at the prompt version actually used
    prompt_fingerprint: str           # short hash of the prompt text itself
    tools: list[ToolBinding] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)  # e.g. "pii-redaction-v2"
    dependencies: list[str] = Field(default_factory=list)  # "other-agent@1.2.0"

    tenant_visibility: TenantVisibility
    review: Review = Field(default_factory=Review)

    changelog: str = ""

    def requested_permission_levels(self) -> set[str]:
        return {t.permission.value for t in self.tools}

    def requests_elevated_permissions(self) -> bool:
        elevated = {PermissionLevel.WRITE, PermissionLevel.DELETE, PermissionLevel.EXTERNAL_NETWORK}
        return any(t.permission in elevated for t in self.tools)
