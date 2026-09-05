from app.governance import evaluate_install
from app.registry import registry
from app.tenancy import is_visible_to_tenant


def test_pending_review_agent_with_elevated_permissions_cannot_be_installed():
    manifest = registry.get_latest("support-triage")
    decision = evaluate_install(manifest)
    assert decision.allowed is False
    assert "elevated permissions" in decision.reason


def test_approved_readonly_agent_can_be_installed():
    manifest = registry.get_version("billing-reconciler", "1.0.0")
    decision = evaluate_install(manifest)
    assert decision.allowed is True


def test_pending_elevated_version_blocked_but_earlier_approved_version_still_installable():
    pending = registry.get_version("billing-reconciler", "2.0.0")
    approved = registry.get_version("billing-reconciler", "1.0.0")
    assert evaluate_install(pending).allowed is False
    assert evaluate_install(approved).allowed is True


def test_governance_approved_version_after_review_is_installable():
    approved_v2 = registry.get_version("billing-reconciler", "2.1.0")
    decision = evaluate_install(approved_v2)
    assert decision.allowed is True


def test_allowlisted_agent_only_visible_to_listed_tenants():
    manifest = registry.get_latest("billing-reconciler")  # allowlist: finance, platform
    assert is_visible_to_tenant(manifest, "finance") is True
    assert is_visible_to_tenant(manifest, "platform") is True
    assert is_visible_to_tenant(manifest, "support") is False
    assert is_visible_to_tenant(manifest, None) is False


def test_denylisted_agent_visible_to_everyone_except_listed_tenants():
    manifest = registry.get_latest("incident-summarizer")  # denylist: support
    assert is_visible_to_tenant(manifest, "support") is False
    assert is_visible_to_tenant(manifest, "sre") is True
    assert is_visible_to_tenant(manifest, "finance") is True


def test_public_agent_visible_to_everyone():
    manifest = registry.get_latest("pr-reviewer")
    assert is_visible_to_tenant(manifest, "any-random-tenant") is True
    assert is_visible_to_tenant(manifest, None) is True


def test_publisher_team_can_always_see_its_own_agent_even_if_private():
    manifest = registry.get_latest("support-triage")  # allowlist: support only
    assert is_visible_to_tenant(manifest, "support") is True
    assert is_visible_to_tenant(manifest, "finance") is False
