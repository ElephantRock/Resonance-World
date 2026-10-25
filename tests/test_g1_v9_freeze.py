"""Freeze-manifest, call-contract, and power-analysis tests (model-free)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance_world.experimental_runtime.g1_v9 import (
    PlanningAssumptions,
    arm_call_contracts,
    budget_summary,
    build_freeze_manifest,
    build_machine,
    default_contract,
    manifest_digest,
    minimum_detectable_delta,
    power,
    sensitivity_table,
    verify_pinned_files,
)
from resonance_world.experimental_runtime.g1_v9.call_contract import (
    MODEL,
    PROVIDER,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_COMMIT = "374249adee81b9909646f54bc544d19cda1dd007"
ACCEPTANCE_KEY_HEX = bytes(range(16, 48)).hex()
EVALUATOR_HEX = bytes(range(48, 80)).hex()


@pytest.fixture(scope="module")
def manifest():
    return build_freeze_manifest(repo_root=REPO_ROOT, code_commit=CODE_COMMIT)


def test_manifest_pins_every_governance_and_source_file(manifest) -> None:
    files = manifest.manifest["scenario_file_hashes"]
    assert len(files) == 12
    ok, mismatched = verify_pinned_files(manifest, REPO_ROOT)
    assert ok is True
    assert mismatched == []


def test_manifest_digest_is_deterministic(manifest) -> None:
    rebuilt = build_freeze_manifest(repo_root=REPO_ROOT, code_commit=CODE_COMMIT)
    assert manifest_digest(manifest) == manifest_digest(rebuilt)


def test_manifest_records_the_budget_split(manifest) -> None:
    budget = manifest.manifest["call_budget"]
    assert budget["decision_slots_per_world"] == 620
    assert budget["model_sends_per_world"] == 420
    assert budget["computational_slots_per_world"] == 200
    assert budget["calls_per_decision"] == 1
    assert budget["retries_or_replacements_allowed"] is False
    assert budget["max_provider_sends_this_gate"] == 0

    per_arm = budget["per_arm"]
    assert per_arm["acquisition"]["decision_slots"] == 100
    assert per_arm["acquisition"]["model_sends_per_world"] == 100
    assert per_arm["arm-d-canonical"]["decision_slots"] == 200
    assert per_arm["arm-d-canonical"]["model_sends_per_world"] == 0
    assert per_arm["arm-c-frozen"]["decision_slots"] == 120


def test_manifest_carries_no_provider_authorization(manifest) -> None:
    provider = manifest.manifest["provider"]
    assert provider["provider"] == PROVIDER
    assert provider["model"] == MODEL
    assert provider["provider_authorized"] is False
    assert provider["authorization_reference"] is None
    assert manifest.manifest["call_budget"]["max_provider_sends_this_gate"] == 0


def test_manifest_contains_no_seed_or_key_material(manifest) -> None:
    text = manifest.to_json()
    assert ACCEPTANCE_KEY_HEX not in text
    assert EVALUATOR_HEX not in text
    blinded = manifest.manifest["blinded_inputs"]
    assert "never" in blinded["evaluator_seed"]
    assert "never" in blinded["commitment_key"]
    assert "sealed ledger" in blinded["hidden_tables"]


def test_manifest_pins_machine_fingerprint_and_contract(manifest) -> None:
    contract = default_contract()
    fingerprint = build_machine(contract).fingerprint()
    assert manifest.manifest["machine_fingerprint"] == fingerprint
    assert manifest.manifest["contract_digest"] == contract.digest()
    assert manifest.manifest["code_commit"] == CODE_COMMIT
    assert manifest.manifest["status"] == "candidate-pre-freeze"


def test_power_analysis_matches_the_closed_form() -> None:
    assumptions = PlanningAssumptions(
        worlds=24,
        decisions_per_arm_post=100,
        mean_accuracy=0.5,
        world_heterogeneity_sd=0.10,
    )
    import math

    expected_sigma_w = math.sqrt(2 * 0.5 * 0.5 / 100)
    assert assumptions.sigma_w == pytest.approx(expected_sigma_w)
    expected_sigma_d = math.sqrt(0.10**2 + expected_sigma_w**2)
    assert assumptions.sigma_d == pytest.approx(expected_sigma_d, rel=1e-9)
    expected_se = expected_sigma_d / math.sqrt(24)
    assert assumptions.standard_error == pytest.approx(expected_se, rel=1e-9)

    # Closed-form power at a large effect is effectively 1; at a small
    # effect it matches the normal-approximation value.
    assert power(assumptions, 0.20) > 0.999
    small = power(assumptions, 0.05)
    from statistics import NormalDist

    nd = NormalDist()
    z_alpha = nd.inv_cdf(0.975)
    shift = 0.05 / assumptions.standard_error
    expected_small = nd.cdf(-z_alpha - shift) + (1 - nd.cdf(z_alpha - shift))
    assert small == pytest.approx(expected_small, abs=1e-12)


def test_power_is_monotonic_in_worlds_and_effect() -> None:
    base = PlanningAssumptions(worlds=12, decisions_per_arm_post=100)
    more = PlanningAssumptions(worlds=48, decisions_per_arm_post=100)
    assert power(more, 0.10) >= power(base, 0.10)
    assert power(base, 0.20) >= power(base, 0.10) >= power(base, 0.05)
    assert minimum_detectable_delta(more) <= minimum_detectable_delta(base)


def test_mde_is_reported_per_heterogeneity_scenario() -> None:
    assumptions = PlanningAssumptions(
        worlds=24,
        decisions_per_arm_post=100,
        world_heterogeneity_sd=0.0,
    )
    # With no world-level heterogeneity, 24 worlds detect well below 20pp.
    assert minimum_detectable_delta(assumptions, 0.8) < 0.10
    rows = sensitivity_table(assumptions)
    assert [row["world_heterogeneity_sd"] for row in rows][0] == 0.0
    mdes = [row["mde_80"] for row in rows]
    assert mdes == sorted(mdes)  # MDE grows with heterogeneity


def test_call_contract_separates_computational_from_model_arms() -> None:
    contract = default_contract()
    arms = arm_call_contracts(contract)
    assert arms["acquisition"].model_backed is True
    assert arms["acquisition"].decision_slots == 100
    assert arms["arm-d-canonical"].model_backed is False
    assert arms["arm-d-canonical"].decision_slots == 200
    for arm in arms.values():
        assert arm.calls_per_decision == 1
        assert arm.retries_or_replacements is False

    totals = budget_summary(contract)
    assert totals == {
        "decision_slots_per_world": 620,
        "model_sends_per_world": 420,
        "computational_slots_per_world": 200,
    }


def test_candidate_manifest_artifact_is_self_consistent() -> None:
    artifact = REPO_ROOT / "research" / "g1_v9" / "freeze-manifest-candidate.json"
    if not artifact.exists():
        pytest.skip("candidate artifact not yet emitted")
    data = json.loads(artifact.read_text(encoding="utf-8"))
    from resonance_world.experimental_runtime.g1_v9.freeze import FreezeManifest

    parsed = FreezeManifest(data["manifest"])
    assert manifest_digest(parsed) == data["digest"]
    manifest = data["manifest"]
    assert manifest["status"] == "candidate-pre-freeze"
    assert manifest["provider"]["provider_authorized"] is False
    assert manifest["call_budget"]["max_provider_sends_this_gate"] == 0
    assert ACCEPTANCE_KEY_HEX not in artifact.read_text(encoding="utf-8")
    assert EVALUATOR_HEX not in artifact.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Review round 5: strict anchor verification and intra-world correlation
# ---------------------------------------------------------------------------


def _git_head(repo_root: Path) -> str:
    import subprocess

    return (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )


def test_anchor_verifier_rejects_placeholder_commit() -> None:
    """Placeholders like WORKING-TREE-CANDIDATE are never valid anchors."""

    from resonance_world.experimental_runtime.g1_v9 import verify_freeze_anchor

    placeholder = build_freeze_manifest(
        repo_root=REPO_ROOT, code_commit="WORKING-TREE-CANDIDATE"
    )
    ok, failures = verify_freeze_anchor(
        placeholder, REPO_ROOT, expected_commit="WORKING-TREE-CANDIDATE"
    )
    assert ok is False
    assert any("40-hex" in failure for failure in failures)


def test_anchor_verifier_accepts_pinned_head_manifest() -> None:
    from resonance_world.experimental_runtime.g1_v9 import verify_freeze_anchor

    head = _git_head(REPO_ROOT)
    pinned = build_freeze_manifest(repo_root=REPO_ROOT, code_commit=head)
    ok, failures = verify_freeze_anchor(
        pinned,
        REPO_ROOT,
        expected_commit=head,
        require_status="candidate-pre-freeze",
    )
    assert ok, failures


def test_anchor_verifier_rejects_commit_content_mismatch(manifest) -> None:
    """A manifest whose hashes claim a different commit must fail."""

    from resonance_world.experimental_runtime.g1_v9 import verify_freeze_anchor
    from resonance_world.experimental_runtime.g1_v9.freeze import FreezeManifest

    tampered = dict(manifest.manifest)
    tampered["code_commit"] = CODE_COMMIT
    # Keep the working-tree file hashes while claiming the review commit:
    # the git-show comparison must catch the mismatch.
    parsed = FreezeManifest(tampered)
    ok, failures = verify_freeze_anchor(parsed, REPO_ROOT, expected_commit=CODE_COMMIT)
    assert ok is False
    assert failures


def test_intra_world_correlation_reproduces_review_table() -> None:
    """P0: the rho sensitivity grid matches the reviewer's arithmetic."""

    from resonance_world.experimental_runtime.g1_v9 import (
        intra_world_correlation_table,
    )

    assumptions = PlanningAssumptions(
        worlds=24,
        decisions_per_arm_post=100,
        mean_accuracy=0.5,
        world_heterogeneity_sd=0.10,
    )
    rows = intra_world_correlation_table(assumptions)
    expected = {
        0.0: (100.0, 0.070),
        0.05: (16.81, 0.114),
        0.10: (9.1743, 0.145),
        0.20: (4.8077, 0.193),
    }
    for row in rows:
        rho = row["decision_correlation_rho"]
        effective, mde = expected[rho]
        assert row["effective_decisions_per_arm"] == pytest.approx(effective, abs=0.05)
        assert row["mde_80"] == pytest.approx(mde, abs=0.002)


def test_statistical_plan_pins_test_ci_and_success_criteria(manifest) -> None:
    plan = manifest.manifest["statistical_plan"]
    assert "paired t-test" in plan["statistical_test"]
    assert "95% t-based" in plan["confidence_interval"]
    assert plan["statistical_success"] == "lower bound of the 95% CI > 0"
    assert "0.20" in plan["practical_success"]
    assert plan["practical_threshold_status"] == "proposed-pending-freeze"
    assert "not replaced" in plan["incomplete_worlds"]
    assert "18" in plan["incomplete_worlds"]


# ---------------------------------------------------------------------------
# Freeze-review round: strict frozen-unauthorized emission
# ---------------------------------------------------------------------------


def test_strict_frozen_mode_fails_closed_on_incomplete_manifests(manifest) -> None:
    """P0: a minimal manifest must never pass the final freeze check."""

    from resonance_world.experimental_runtime.g1_v9 import (
        FROZEN_UNAUTHORIZED_STATUS,
        verify_freeze_anchor,
    )
    from resonance_world.experimental_runtime.g1_v9.freeze import FreezeManifest

    incomplete = {
        "schema": "g1-v9-freeze-manifest-v1",
        "status": FROZEN_UNAUTHORIZED_STATUS,
        "code_commit": CODE_COMMIT,
        "scenario_file_hashes": [],  # empty list must be rejected
        "provider": {"provider_authorized": True},  # must be rejected
        "call_budget": {"max_provider_sends_this_gate": 50},  # must be rejected
    }
    parsed = FreezeManifest(incomplete)
    ok, failures = verify_freeze_anchor(
        parsed,
        REPO_ROOT,
        expected_commit=CODE_COMMIT,
        strict_frozen=True,
    )
    assert ok is False
    joined = "; ".join(failures)
    assert "missing mandatory freeze field" in joined
    assert "empty" in joined
    assert "provider_authorized must be false" in joined
    assert "send cap must be zero" in joined


def test_strict_frozen_mode_accepts_a_valid_final_emission() -> None:
    """P0: a complete frozen-unauthorized emission verifies end to end."""

    from resonance_world.experimental_runtime.g1_v9 import (
        FROZEN_UNAUTHORIZED_STATUS,
        verify_freeze_anchor,
    )
    from resonance_world.experimental_runtime.g1_v9.freeze import FreezeManifest

    head = _git_head(REPO_ROOT)
    built = build_freeze_manifest(
        repo_root=REPO_ROOT,
        code_commit=head,
        status=FROZEN_UNAUTHORIZED_STATUS,
    )
    artifact = json.loads(built.to_json())
    ok, failures = verify_freeze_anchor(
        FreezeManifest(artifact["manifest"]),
        REPO_ROOT,
        expected_commit=head,
        strict_frozen=True,
        outer_digest=artifact["digest"],
        require_status=FROZEN_UNAUTHORIZED_STATUS,
        expected_machine_fingerprint=artifact["manifest"]["machine_fingerprint"],
        expected_contract_digest=artifact["manifest"]["contract_digest"],
    )
    assert ok, failures


def test_frozen_unauthorized_artifact_is_strictly_valid() -> None:
    """The final emission must pass the strict frozen verification."""

    artifact = (
        REPO_ROOT / "research" / "g1_v9" / "freeze-manifest-frozen-unauthorized.json"
    )
    if not artifact.exists():
        pytest.skip("final frozen-unauthorized artifact not yet emitted")
    from resonance_world.experimental_runtime.g1_v9 import (
        FROZEN_UNAUTHORIZED_STATUS,
        verify_freeze_anchor,
    )
    from resonance_world.experimental_runtime.g1_v9.freeze import FreezeManifest

    data = json.loads(artifact.read_text(encoding="utf-8"))
    parsed = FreezeManifest(data["manifest"])
    assert manifest_digest(parsed) == data["digest"]
    assert data["manifest"]["status"] == FROZEN_UNAUTHORIZED_STATUS
    assert data["manifest"]["provider"]["provider_authorized"] is False
    ok, failures = verify_freeze_anchor(
        parsed,
        REPO_ROOT,
        expected_commit=data["manifest"]["code_commit"],
        strict_frozen=True,
        outer_digest=data["digest"],
        require_status=FROZEN_UNAUTHORIZED_STATUS,
    )
    assert ok, failures


def test_governance_entry_carries_attester_and_utc_time() -> None:
    """P1: governance entries carry the attester and a UTC timestamp."""

    from datetime import datetime

    from resonance_world.experimental_runtime.g1_v9 import (
        governance_entry,
        validate_governance_entry,
    )

    entry = governance_entry(
        manifest=build_freeze_manifest(repo_root=REPO_ROOT, code_commit=CODE_COMMIT),
        action="frozen-unauthorized",
        recorded_by="operator",
    )
    failures = validate_governance_entry(entry)
    assert failures == []
    datetime.fromisoformat(entry["recorded_at"])
    assert entry["recorded_by"] == "operator"

    with pytest.raises(ValueError, match="recorded_by"):
        governance_entry(
            manifest=build_freeze_manifest(repo_root=REPO_ROOT, code_commit=CODE_COMMIT),
            action="frozen-unauthorized",
            recorded_by="   ",
        )
    with pytest.raises(ValueError, match="governance action"):
        governance_entry(
            manifest=build_freeze_manifest(repo_root=REPO_ROOT, code_commit=CODE_COMMIT),
            action="self-promoted",
            recorded_by="operator",
        )
