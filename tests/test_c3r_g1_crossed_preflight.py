"""Zero-provider negative checks of G1 crossed history isolation."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_preflight import (
    PHASES,
    SessionBinding,
    SourceObservation,
    build_preflight,
)


def fixture():
    plan = make_plan()
    sources = tuple(SourceObservation(c.unit_id, task.task_id, "A", "incorrect")
                    for c in plan.cells for task in c.development)
    sessions = tuple(SessionBinding(c.unit_id, phase, f"isolated-{c.unit_id}-{phase}")
                     for c in plan.cells for phase in PHASES)
    return plan, sources, sessions


def test_views_hide_all_source_answers_from_neutral_and_fresh() -> None:
    plan, sources, sessions = fixture()
    bundle = build_preflight(plan, sources=sources, sessions=sessions)
    assert len(bundle.views) == 24
    assert bundle.audit["physical_sends"] == 0
    assert bundle.audit["live_ready"] is False
    assert bundle.audit["source_evaluator_receipts_attested"] is False
    assert bundle.audit["provider_session_isolation_attested"] is False
    assert bundle.audit["local_tokenizer_comparisons"] == 0
    assert "feedback" not in json.dumps(bundle.audit)
    for view in bundle.views:
        payload = json.loads(view.payload)
        assert "target" not in view.payload
        assert "truth" not in view.payload
        assert payload["qualification_task"]["stage"] == "qualification"
        history = payload["source_history"]
        if view.arm == "learned":
            assert len(history) == 2
            assert all(h["feedback"] == "incorrect" and h["action"] == "A"
                       for h in history)
        elif view.arm == "neutral":
            assert len(history) == 2
            assert all(set(h) == {"public_task", "attempt_recorded"} for h in history)
            assert all(h["attempt_recorded"] is True for h in history)
        else:
            assert view.arm == "fresh" and history == []


def test_source_errors_fail_closed() -> None:
    plan, sources, sessions = fixture()
    for bad in (sources[:-1], (*sources[:-1], sources[0]),
                (*sources[:-1], replace(sources[-1], task_id="holdout-injected"))):
        with pytest.raises(ValueError, match="development evidence"):
            build_preflight(plan, sources=bad, sessions=sessions)
    with pytest.raises(ValueError, match="exact A/B"):
        build_preflight(plan, sources=(replace(sources[0], action="B / prompt injection"),
                                       *sources[1:]), sessions=sessions)
    with pytest.raises(ValueError, match="binary feedback"):
        build_preflight(plan, sources=(replace(sources[0], feedback="B is true"),
                                       *sources[1:]), sessions=sessions)


def test_repeated_or_missing_session_declarations_fail_closed() -> None:
    plan, sources, sessions = fixture()
    with pytest.raises(ValueError, match="globally disjoint"):
        build_preflight(plan, sources=sources, sessions=sessions[:-1])
    with pytest.raises(ValueError, match="globally disjoint"):
        build_preflight(plan, sources=sources, sessions=(replace(
            sessions[0], session_ref=sessions[1].session_ref), *sessions[1:]))
    with pytest.raises(ValueError, match="globally disjoint"):
        build_preflight(plan, sources=sources, sessions=(replace(
            sessions[0], phase="learned"), *sessions[1:]))


def test_local_tokenizer_is_diagnostic_not_provider_parity() -> None:
    plan, sources, sessions = fixture()
    bundle = build_preflight(plan, sources=sources, sessions=sessions,
                             token_count=lambda p: len(p.encode("utf-8")))
    assert bundle.audit["local_tokenizer_comparisons"] == 8
    assert bundle.audit["local_tokenizer_equal_pairs"] < 8
    assert bundle.audit["provider_prompt_token_parity_attested"] is False
    assert bundle.audit["live_ready"] is False
    with pytest.raises(ValueError, match="nonnegative integer"):
        build_preflight(plan, sources=sources, sessions=sessions,
                        token_count=lambda _p: True)


def test_different_feedback_never_changes_neutral_or_fresh() -> None:
    plan, sources, sessions = fixture()
    first = build_preflight(plan, sources=sources, sessions=sessions)
    flipped = tuple(replace(s, action="B", feedback="correct") for s in sources)
    second = build_preflight(plan, sources=flipped, sessions=sessions)
    for a, b in zip(first.views, second.views, strict=True):
        assert a.arm == b.arm
        if a.arm != "learned":
            assert a.payload == b.payload
        else:
            assert a.payload != b.payload


def test_modified_plan_cannot_smuggle_target_data() -> None:
    plan, sources, sessions = fixture()
    cells = list(plan.cells)
    cell = cells[4]  # a text-family cell; the schedule keeps its original IDs
    source = list(cell.development)
    source[0] = replace(source[0], operands="ab-target-B-secret-ab")
    cells[4] = replace(cell, development=tuple(source))
    contaminated = replace(plan, cells=tuple(cells))
    contaminated.audit()  # Structurally valid does not mean pre-frozen.
    with pytest.raises(ValueError, match="unfrozen crossed plan digest"):
        build_preflight(contaminated, sources=sources, sessions=sessions)
