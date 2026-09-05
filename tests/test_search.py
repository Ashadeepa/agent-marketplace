from app.registry import registry
from app.search import score_agents


def test_query_matches_capability_even_without_exact_name_overlap():
    """'reconcile invoices' should surface billing-reconciler even though neither word is in
    the *name* 'Billing Reconciler' verbatim as a query token — it's a capability + synonym match."""
    agents = registry.all_latest()
    hits = score_agents("reconcile invoices", agents)
    assert hits, "expected at least one hit"
    assert hits[0].manifest.agent_id == "billing-reconciler"


def test_capability_query_ranks_the_matching_agent_first():
    agents = registry.all_latest()
    hits = score_agents("triage support tickets", agents)
    assert hits[0].manifest.agent_id == "support-triage"
    assert "triage-tickets" in hits[0].matched_capabilities


def test_empty_query_returns_all_agents_with_approved_first():
    agents = registry.all_latest()
    hits = score_agents("", agents)
    assert len(hits) == len(agents)
    # pr-reviewer and incident-summarizer and billing-reconciler are approved+verified;
    # support-triage is pending_review+unverified and should sort after them.
    ids_in_order = [h.manifest.agent_id for h in hits]
    assert ids_in_order.index("support-triage") == len(ids_in_order) - 1


def test_nonsense_query_returns_no_hits():
    agents = registry.all_latest()
    hits = score_agents("xyzzy quux nonexistent", agents)
    assert hits == []
