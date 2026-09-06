from __future__ import annotations

import json
from pathlib import Path

POLICY = Path("configs/autonomous-operating-charter-v0.1.json")
README = Path("README.md")
CHARTER = Path("docs/autonomous-operating-charter-v0.1.md")


def test_machine_readable_autonomous_charter_preserves_constitutional_boundaries() -> None:
    policy = json.loads(POLICY.read_text())
    resources = policy["resources"]
    scientific = policy["scientific_invariants"]
    merge_policy = policy["autonomous_merge_policy"]
    review_policy = policy["review_policy"]

    assert policy["schema"] == "resonance-world-autonomous-operating-charter-v0.1"
    assert policy["status"] == "active_when_human_approved_and_merged_to_main"
    assert resources["default_external_discretionary_spend_usd"] == 0
    assert resources[
        "campaign_provider_calls_require_explicit_authorization_even_if_free"
    ] is True
    assert scientific["outcome_based_confirmatory_retuning_allowed"] is False
    assert scientific["apparatus_failure_is_negative_mechanism_result"] is False
    assert scientific["production_historical_substrate_enabled"] is False
    assert review_policy["self_review_substitutes_for_scientific_acceptance"] is False

    forbidden = set(merge_policy["forbidden_authority_mutations"])
    assert "frozen_scientific_contract" in forbidden
    assert "mechanism_registry_status" in forbidden
    assert "provider_authorization" in forbidden
    assert "autonomous_operating_charter" in forbidden
    assert "constitutional_governance" in forbidden
    assert merge_policy["requires_no_unauthorized_provider_execution"] is True


def test_charter_is_discoverable_and_requires_human_activation() -> None:
    readme = README.read_text()
    charter = CHARTER.read_text()

    assert "docs/autonomous-operating-charter-v0.1.md" in readme
    assert "configs/autonomous-operating-charter-v0.1.json" in readme
    assert "active only after human-approved merge" in charter
    assert "This charter PR itself is not autonomously merge-eligible" in charter
    assert "Production/default Historical Substrate remains **OFF**" in charter
