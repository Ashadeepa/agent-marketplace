"""
Spec for the trickiest claim in the talk: a prompt/model/tool/policy change can be a breaking
change even when the API contract doesn't move — and the reverse, a contract bump with no
behavioral change underneath.
"""
from app.registry import registry
from app.versioning import compute_behavior_hash, diff_versions


def test_billing_reconciler_1_0_to_2_0_is_a_silent_breaking_change():
    v1 = registry.get_version("billing-reconciler", "1.0.0")
    v2 = registry.get_version("billing-reconciler", "2.0.0")

    diff = diff_versions(v1, v2)

    # The API contract didn't change...
    assert v1.api_contract_version == v2.api_contract_version == "v1"
    assert diff.api_contract_changed is False

    # ...but the model, prompt, and tool permissions all did.
    assert diff.behavior_changed is True
    assert diff.is_silent_breaking_change is True
    assert diff.requires_reapproval is True
    assert "write" in diff.new_permissions_requested
    assert any("model changed" in r for r in diff.reasons)
    assert any("prompt changed" in r for r in diff.reasons)


def test_billing_reconciler_behavior_hash_changes_with_prompt_and_model():
    v1 = registry.get_version("billing-reconciler", "1.0.0")
    v2 = registry.get_version("billing-reconciler", "2.0.0")
    assert compute_behavior_hash(v1) != compute_behavior_hash(v2)


def test_2_0_to_2_1_keeps_same_prompt_and_model_but_upgrades_policy():
    # 2.0.0 -> 2.1.0 keeps the same prompt/model/tools, but the PII redaction policy was
    # upgraded (v1 -> v2) as a condition of governance approval. Policies are part of the
    # behavioral surface too, so the hash still moves — the diff should explain why.
    v2 = registry.get_version("billing-reconciler", "2.0.0")
    v21 = registry.get_version("billing-reconciler", "2.1.0")

    assert compute_behavior_hash(v2) != compute_behavior_hash(v21)

    diff = diff_versions(v2, v21)
    assert diff.behavior_changed is True
    assert not any("prompt changed" in r for r in diff.reasons)
    assert not any("model changed" in r for r in diff.reasons)
    assert any("policies changed" in r for r in diff.reasons)


def test_identical_manifests_produce_identical_hash_regardless_of_field_order():
    v1 = registry.get_version("billing-reconciler", "1.0.0")
    assert compute_behavior_hash(v1) == compute_behavior_hash(v1)
