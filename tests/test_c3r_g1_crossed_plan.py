"""Credential-free, zero-provider regressions for G1 crossed offline cohort."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from resonance_world.c3r_g1_crossed_plan import (
    AttemptSlot,
    evaluator_private_assignment,
    local_private_balance_audit,
    make_plan,
)


def test_public_design_is_crossed_and_reproducible() -> None:
    plan = make_plan()
    assert plan.public_digest == make_plan().public_digest
    assert plan.public_lock()["prescribed_logical_attempts"] == 40
    assert plan.audit()["development_attempts"] == 16
    assert plan.audit()["qualification_attempts"] == 24
    assert plan.audit()["heldout_triplets"] == 8
    assert len(plan.schedule) == 40
    assert plan.public_lock()["physical_send_authorized"] is False
    assert plan.public_lock()["scientific_acceptance"] is False
    assert plan.public_lock()["provider_token_parity_attested"] is False
    assert plan.audit()["physical_sends"] == 0
    assert len({c.unit_id for c in plan.cells}) == 8
    assert len({c.context_id for c in plan.cells}) == 8
    assert all(c.development[0].action_value("A") !=
               c.development[0].action_value("B") for c in plan.cells)
    assert all(c.qualification[0].action_value("A") !=
               c.qualification[0].action_value("B") for c in plan.cells)
    assert all(s.stage == "development" for s in plan.schedule[:16])
    assert all(s.stage == "qualification" for s in plan.schedule[16:])
    assert {slot.arm for slot in plan.schedule[16:]} == {
        "learned", "fresh", "neutral"
    }


def test_private_evaluator_balance_without_exposing_targets() -> None:
    plan = make_plan()
    secret = bytes(range(32))  # conspicuously synthetic fixture, not a production key
    private = evaluator_private_assignment(plan, secret=secret)
    audit = local_private_balance_audit(plan, private)
    assert audit["family_target_quota"] == {
        "arithmetic": {"A": 2, "B": 2},
        "text": {"A": 2, "B": 2},
    }
    assert audit["independent_evaluator_attested"] is False
    assert json.dumps(plan.public_lock()).find("private_seed") == -1
    assert not any(key in plan.public_lock() for key in ("targets", "assignment"))
    for context, target in private.items():
        assert target in ("A", "B")
        assert context not in audit["family_target_quota"]


def test_private_balance_rejects_missing_malformed_and_unbalanced() -> None:
    plan = make_plan()
    with pytest.raises(ValueError, match="32"):
        evaluator_private_assignment(plan, secret=b"too-short")
    mapping = evaluator_private_assignment(plan, secret=bytes(range(32)))
    with pytest.raises(ValueError, match="context set"):
        local_private_balance_audit(plan, {"not-a-context": "A"})
    with pytest.raises(ValueError, match="invalid private"):
        local_private_balance_audit(plan, {**mapping, next(iter(mapping)): "?"})
    with pytest.raises(ValueError, match="2 A and 2 B"):
        local_private_balance_audit(plan, dict.fromkeys(mapping, "A"))


def test_mutated_attempt_list_fails_closed() -> None:
    plan = make_plan()
    with pytest.raises(ValueError, match="exactly once"):
        replace(plan, schedule=plan.schedule[:-1]).audit()
    with pytest.raises(ValueError, match="exactly once"):
        replace(plan, schedule=(*plan.schedule[:-1], plan.schedule[0])).audit()
    with pytest.raises(ValueError, match="precede"):
        schedule = list(plan.schedule)
        schedule[0], schedule[16] = schedule[16], schedule[0]
        replace(plan, schedule=tuple(schedule)).audit()
    with pytest.raises(ValueError, match="reused task"):
        cells = list(plan.cells)
        tasks = list(cells[1].development)
        tasks[0] = replace(tasks[0], operands=cells[0].development[0].operands)
        cells[1] = replace(cells[1], development=tuple(tasks))
        replace(plan, cells=tuple(cells)).audit()
    with pytest.raises(ValueError, match="exact A/B"):
        plan.cells[0].development[0].action_value("X")


def test_no_provider_coupling_or_implicit_run_authorization(monkeypatch) -> None:
    # Even if an unrelated credential is present, the constructor performs
    # only deterministic local planning and retains no credential or responses.
    monkeypatch.setenv("C3R_ZAI_API_KEY", "synthetic-do-not-send")
    plan = make_plan()
    assert "synthetic-do-not-send" not in json.dumps(plan.public_lock())
    assert "provider" not in str(AttemptSlot.__annotations__).lower()
    assert plan.audit()["scientific_acceptance"] is False
