"""
Trust & governance.

Decides whether an install/invoke is *allowed*, as distinct from whether the agent is *findable*
(that's tenancy.py). The rule modeled here: elevated-permission agents (write / delete / external
network) must be in ReviewStatus.APPROVED before anyone can install them — draft and
pending_review agents can be discovered and inspected (so teams can request review) but not
installed. Publisher verification and eval results are surfaced as trust signals in the UI even
when they aren't hard gates, the same way a package registry shows download counts and audit
badges without necessarily blocking on them.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import AgentManifest, ReviewStatus


@dataclass
class GovernanceDecision:
    allowed: bool
    reason: str


def evaluate_install(manifest: AgentManifest) -> GovernanceDecision:
    if manifest.review.status == ReviewStatus.REJECTED:
        return GovernanceDecision(False, "Agent was rejected in review and cannot be installed.")

    if manifest.review.status == ReviewStatus.DEPRECATED:
        return GovernanceDecision(False, "Agent version is deprecated. Install the latest approved version.")

    if manifest.requests_elevated_permissions() and manifest.review.status != ReviewStatus.APPROVED:
        elevated = sorted(
            {t.permission.value for t in manifest.tools if t.permission.value != "read"}
        )
        return GovernanceDecision(
            False,
            f"Agent requests elevated permissions {elevated} but review status is "
            f"'{manifest.review.status.value}', not 'approved'. Elevated-permission agents require "
            f"approval before install.",
        )

    if manifest.review.status == ReviewStatus.DRAFT:
        return GovernanceDecision(False, "Agent is still in draft and has not entered review.")

    if manifest.review.evals.safety == "fail":
        return GovernanceDecision(False, "Agent failed its most recent safety evaluation.")

    return GovernanceDecision(True, "Install allowed.")


def trust_badges(manifest: AgentManifest) -> list[str]:
    """Signals surfaced in the UI — informational, not gating (except where evaluate_install says so)."""
    badges = []
    if manifest.publisher.verified:
        badges.append("Verified publisher")
    if manifest.review.status == ReviewStatus.APPROVED:
        badges.append("Approved")
    elif manifest.review.status == ReviewStatus.PENDING_REVIEW:
        badges.append("Pending review")
    elif manifest.review.status == ReviewStatus.DEPRECATED:
        badges.append("Deprecated")
    if manifest.review.evals.safety == "pass":
        badges.append("Safety eval: pass")
    if manifest.review.evals.accuracy is not None:
        badges.append(f"Accuracy: {manifest.review.evals.accuracy:.0%}")
    if manifest.requests_elevated_permissions():
        badges.append("Requests elevated permissions")
    return badges
