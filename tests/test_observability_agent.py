from app.governance import evaluate_install, trust_badges
from app.registry import registry
from app.search import score_agents
from app.tenancy import is_visible_to_tenant


def test_observability_agent_is_registered():
    manifest = registry.get_latest("observability-agent")
    assert manifest is not None
    assert manifest.version == "1.0.0"


def test_observability_agent_query_ranks_it_first():
    agents = registry.all_latest()
    hits = score_agents("detect anomalies in metrics", agents)
    assert hits[0].manifest.agent_id == "observability-agent"
    assert "detect-anomalies" in hits[0].matched_capabilities


def test_observability_agent_is_public():
    manifest = registry.get_latest("observability-agent")
    assert is_visible_to_tenant(manifest, "any-random-tenant") is True
    assert is_visible_to_tenant(manifest, None) is True


def test_observability_agent_requests_no_elevated_permissions():
    manifest = registry.get_latest("observability-agent")
    assert manifest.requests_elevated_permissions() is False
    assert manifest.requested_permission_levels() == {"read"}


def test_observability_agent_is_installable():
    manifest = registry.get_latest("observability-agent")
    decision = evaluate_install(manifest)
    assert decision.allowed is True
    assert decision.reason == "Install allowed."


def test_observability_agent_trust_badges():
    manifest = registry.get_latest("observability-agent")
    badges = trust_badges(manifest)
    assert "Verified publisher" in badges
    assert "Approved" in badges
    assert "Safety eval: pass" in badges
    assert "Requests elevated permissions" not in badges
