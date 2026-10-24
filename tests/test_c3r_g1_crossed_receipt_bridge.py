"""Offline negative tests for the existing chained Ed25519 receipt protocol."""

from __future__ import annotations

import copy
import hashlib
import json
import os

import pytest

from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_preflight import PHASES, SessionBinding, build_preflight
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

_RUN_ID = "g1x-crossed-fixture-20261022"


def _fixture(status_overrides=None):
    plan = make_plan()
    signer = ReceiptSigner(os.urandom(32), run_id=_RUN_ID)
    envelopes = []
    status_overrides = status_overrides or {}
    for i, slot in enumerate(plan.schedule):
        payload = {
            "schema": "c3r-g1-crossed-attempt-v0.1",
            "plan_digest": plan.public_digest,
            "slot_index": i,
            "unit_id": slot.unit_id,
            "task_id": slot.task_id,
            "stage": slot.stage,
            "arm": slot.arm,
            "status": "accepted",
            "action": "B" if i % 4 == 0 else "A",
            "correct": i % 3 == 0,
            "output_sha256": hashlib.sha256(f"fixture-{i}".encode()).hexdigest(),
        }
        payload.update(status_overrides.get(i, {}))
        envelopes.append(signer.seal(payload))
    head = hashlib.sha256(
        json.dumps(envelopes[15], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return plan, signer.public_key_hex, tuple(envelopes), head


def _check(plan, public, records, head=None, mode="terminal", run_id=_RUN_ID):
    return verify_crossed_receipt_chain(
        plan, receipts=records, mode=mode, expected_run_id=run_id,
        pinned_evaluator_public_key_hex=public,
        expected_source_chain_head_sha256=head,
    )


def test_signed_development_integrates_with_grade_isolated_preflight() -> None:
    plan, public, items, _ = _fixture()
    verified = _check(plan, public, items[:16], mode="development")
    assert verified.sources is not None and len(verified.sources) == 16
    assert verified.outcomes is None
    sessions = tuple(SessionBinding(c.unit_id, phase, f"local-{c.unit_id}-{phase}")
                     for c in plan.cells for phase in PHASES)
    bundle = build_preflight(plan, sources=verified.sources, sessions=sessions)
    assert len(bundle.views) == 24
    assert bundle.audit["live_ready"] is False


def test_terminal_chain_binds_all_40_attempts_without_scientific_promotion() -> None:
    plan, public, items, head = _fixture()
    result = _check(plan, public, items, head=head)
    assert len(result.outcomes) == 40
    assert result.source_chain_head_sha256 == head
    assert result.audit["receipt_chain_length_verified"] == 40
    assert result.audit["descriptive"]["prescribed_logical_attempts"] == 40
    assert result.audit["source_chain_head_verified_against_external_pin"] is True
    assert result.audit["evaluator_key_independence_attested"] is False
    assert result.audit["provider_sends_verified"] is False
    assert result.audit["scientific_acceptance"] is False


def test_wrong_evaluator_key_or_cross_run_replay_rejected() -> None:
    plan, public, items, head = _fixture()
    other = ReceiptSigner(os.urandom(32), run_id=_RUN_ID)
    with pytest.raises(ValueError):
        _check(plan, other.public_key_hex, items, head=head)
    with pytest.raises(ValueError):
        _check(plan, public, items, head=head, run_id="different-run-20261022")


def test_missing_duplicated_reordered_and_tampered_chains_rejected() -> None:
    plan, public, items, head = _fixture()
    tampered = copy.deepcopy(items)
    tampered[16]["payload"]["correct"] = not tampered[16]["payload"]["correct"]
    for bad in (tuple(tampered), items[:-1],
                items[:20] + items[19:20] + items[21:],
                items[:19] + (items[20], items[19]) + items[21:]):
        with pytest.raises(ValueError):
            _check(plan, public, bad, head=head)


def test_even_correctly_signed_undeclared_or_wrong_slot_payload_rejected() -> None:
    for alteration in ({"slot_index": 1}, {"target_truth": "A"},
                       {"arm": "fresh"}, {"output_sha256": "0" * 64}):
        plan, public, items, head = _fixture({0: alteration})
        with pytest.raises(ValueError):
            _check(plan, public, items, head=head)


def test_terminal_requires_separately_saved_source_commitment() -> None:
    plan, public, items, head = _fixture()
    for wrong in (None, "0" * 64):
        with pytest.raises(ValueError, match="source chain head"):
            _check(plan, public, items, head=wrong)
    assert _check(plan, public, items, head=head).audit["scientific_acceptance"] is False


def test_signed_but_missing_grade_blocks_preflight_without_shrinking_denominator() -> None:
    plan, public, items, head = _fixture({0: {
        "status": "not_sent", "action": None, "correct": None,
        "output_sha256": None,
    }})
    with pytest.raises(ValueError, match="sixteen accepted"):
        _check(plan, public, items[:16], mode="development")
    report = _check(plan, public, items, head=head)
    assert report.audit["descriptive"]["logical_status_counts"]["not_sent"] == 1
    assert report.audit["descriptive"]["source_units_with_two_accepted_development_actions"] == 7


def test_signed_wrong_data_shape_rejected() -> None:
    plan, public, items, head = _fixture({0: {"correct": 1}})
    with pytest.raises(ValueError, match="accepted signed attempt"):
        _check(plan, public, items, head=head)


def test_no_evidence_gate_is_open_from_local_signatures() -> None:
    plan, public, items, head = _fixture()
    audit = _check(plan, public, items, head=head).audit
    for flag in (
        "source_chain_head_external_custody_attested", "evaluator_key_independence_attested",
        "private_grade_correctness_verified", "provider_sends_verified",
        "session_isolation_verified", "holdout_temporal_closure_attested",
        "provider_token_parity_verified", "scientific_acceptance", "live_ready",
    ):
        assert audit[flag] is False
    assert audit["physical_sends_performed_by_this_verifier"] == 0
