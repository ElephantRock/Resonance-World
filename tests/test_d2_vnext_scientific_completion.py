from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import qualify_d2_vnext_scientific_completion as q


def test_frozen_request_plan_matches_code_contract() -> None:
    plan = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "research"
            / "d2_vnext_scientific_completion"
            / "D2_VNEXT_SCIENTIFIC_COMPLETION_REQUEST_PLAN.json"
        ).read_text()
    )
    q.validate_plan(plan)


def test_materialized_topology_matches_committed_file() -> None:
    root = Path(__file__).resolve().parents[1]
    committed = json.loads(
        (
            root
            / "research"
            / "d2_vnext_scientific_completion"
            / "D2_VNEXT_SCIENTIFIC_COMPLETION_TOPOLOGY.json"
        ).read_text()
    )
    assert q.materialize_topology() == committed
    assert committed["profile_logical_calls"] == 12
    assert committed["trajectory_logical_calls_total"] == 220
    assert committed["trajectory_max_concurrency"] == 4
    assert committed["maximum_registered_logical_calls"] == 232
    assert committed["maximum_physical_sends_total"] == 400


def test_each_trajectory_has_exact_d2_vnext_s1_call_topology() -> None:
    for index in range(4):
        specs = q.trajectory_specs(index)
        assert len(specs) == 55
        by_arm: dict[str, int] = {}
        for spec in specs:
            by_arm[spec["arm"]] = by_arm.get(spec["arm"], 0) + 1
        assert by_arm == {
            "fresh": 4,
            "developed_40": 9,
            "developed_80": 14,
            "developed_160": 24,
            "oracle": 4,
        }


def test_call_shapes_are_deterministic_non_scientific_and_distinct() -> None:
    hashes = set()
    for index, shape in enumerate(q.SHAPES):
        prompt_a = q.user_prompt(shape, 100 + index, "S" * 320)
        prompt_b = q.user_prompt(shape, 100 + index, "S" * 320)
        assert prompt_a == prompt_b
        assert "engineering-only" in prompt_a
        assert "no hidden scientific policy" in prompt_a
        assert "scientifically scored" in prompt_a
        hashes.add(q.sha(prompt_a))
    assert len(hashes) == 4


def test_profile_pass_requires_every_call_and_profile_iteration_bound() -> None:
    profile = q.PROFILES[0]
    good = [
        {
            "status": "success",
            "completed": True,
            "agent_api_calls_observed": 1,
            "provider_http_attempts_observed": 1,
            "terminal_http_429_code_1113": False,
        }
        for _ in range(4)
    ]
    assert q.profile_pass(profile, good)
    bad = [dict(row) for row in good]
    bad[2]["agent_api_calls_observed"] = 3
    assert not q.profile_pass(profile, bad)


def test_strict_response_contract_accepts_only_eight_registered_actions() -> None:
    valid = json.dumps(
        {
            "actions": [
                "KAPPA",
                "MICA",
                "ORBIT",
                "VELA",
                "KAPPA",
                "MICA",
                "ORBIT",
                "VELA",
            ],
            "strategy": "engineering sentinel",
        }
    )
    strategy = q.parse_response(valid)
    assert strategy == "engineering sentinel"

    invalid = json.dumps({"actions": ["KAPPA"] * 7})
    try:
        q.parse_response(invalid)
    except ValueError as exc:
        assert "actions" in str(exc)
    else:
        raise AssertionError("seven-action response unexpectedly accepted")


def test_physical_send_guard_fails_closed_per_logical_call_and_url() -> None:
    budget = q.Budget()
    budget.begin(0)
    for _ in range(q.MAX_SENDS_PER_LOGICAL):
        budget.reserve(q.base.BASE_URL + "/chat/completions")
    try:
        budget.reserve(q.base.BASE_URL + "/chat/completions")
    except q.PhysicalSendBudgetExceeded:
        pass
    else:
        raise AssertionError("55th send on one logical call unexpectedly accepted")

    budget.begin(1)
    try:
        budget.reserve("https://example.com/not-registered")
    except q.UnexpectedOutboundRequest:
        pass
    else:
        raise AssertionError("unregistered outbound URL unexpectedly accepted")


def test_preflight_marker_contract_is_credential_free_by_design() -> None:
    assert q.AUTH_ENV == "D2_VNEXT_SCIENTIFIC_COMPLETION_AUTHORIZED"
    assert q.MAX_SENDS_TOTAL == 400
    assert q.MAX_LOGICAL_CALLS == 232
    assert q.MARKER.name == "RUN_D2_VNEXT_SCIENTIFIC_COMPLETION_QUALIFICATION"
