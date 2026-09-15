# ruff: noqa: I001,E501
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import d2_canonical_json_prompt_agent as agent  # noqa: E402
import d2_canonical_json_prompt_contract as contract  # noqa: E402

from resonance_world import d2_terminal_adapter as exact_adapter  # noqa: E402

def _valid_payload(**extra: object) -> str:
    payload: dict[str, object] = {
        "actions": ["KAPPA", "MICA", "ORBIT", "VELA"] * 2,
        "strategy": "bounded",
    }
    payload.update(extra)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

def test_frozen_contract_and_fresh_probe_balance() -> None:
    rows = contract.validate_frozen_contract()
    assert len(rows) == 72
    assert len({row["probe_id"] for row in rows}) == 72
    assert len({row["seed"] for row in rows}) == 72
    assert min(row["seed"] for row in rows) >= 4_300_000

def test_system_prompt_contains_only_registered_prompt_intervention() -> None:
    prompt = contract.system_prompt()
    assert contract.sha(prompt) == contract.SYSTEM_PROMPT_SHA256
    assert 'JSON square-bracket array of exactly 8 strings' in prompt
    assert 'Never return actions as an object, map, string, keyed per-case record, or scalar' in prompt
    assert 'Each array position corresponds to the matching presented case in order' in prompt
    assert 'Shape example only (not an answer key; do not copy these choices)' in prompt
    assert '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}' in prompt
    assert 'Choose actions for the actual presented cases' in prompt

def test_exact_parser_remains_unchanged_and_rejects_extra_keys() -> None:
    assert exact_adapter.parse_response(_valid_payload())[0] is True
    assert exact_adapter.parse_response(_valid_payload(note="x"))[0] is False
    assert contract.bounded_parse_diagnostic(_valid_payload(note="x")) == "extra_keys"

def test_exact_parser_rejects_actions_object_without_projection_or_coercion() -> None:
    text = json.dumps({"actions": {"0": "KAPPA", "1": "MICA"}})
    assert exact_adapter.parse_response(text)[0] is False
    assert contract.bounded_parse_diagnostic(text) == "actions_not_list"

def test_diagnostics_match_exact_parser_on_representative_rejections() -> None:
    samples = [
        "not-json",
        json.dumps(["KAPPA"] * 8),
        json.dumps({"strategy": "x"}),
        json.dumps({"actions": ["KAPPA"] * 7}),
        json.dumps({"actions": ["NOPE"] * 8}),
        json.dumps({"actions": ["KAPPA"] * 8, "strategy": 4}),
        json.dumps({"actions": ["KAPPA"] * 8, "strategy": "x" * 513}),
    ]
    for text in samples:
        valid, _ = exact_adapter.parse_response(text)
        assert valid is False
        assert contract.bounded_parse_diagnostic(text) != "exact_valid"

def test_request_override_remains_json_object_only() -> None:
    override = agent.request_overrides(17)
    assert override["response_format"] == {"type": "json_object"}
    assert override["extra_body"] == {"thinking": {"type": "disabled"}}
    assert override["extra_headers"][contract.PROBE_ORIGIN_HEADER] == "17"

def test_preflight_is_deterministic_and_provider_free() -> None:
    first = agent.preflight()
    second = agent.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["execution_marker_absent"] is True
    assert first["issue"] == 270
    assert first["probe_count"] == 72
    assert first["parser_intervention"] == "none_unchanged_exact_eight_action_contract"

def test_terminal_adapter_semantics_remain_unchanged() -> None:
    decision = exact_adapter.evaluate_terminal_completion(
        {
            "completed": False,
            "failed": False,
            "partial": False,
            "interrupted": False,
            "error": None,
            "api_calls": 2,
            "final_response": "bounded-nonempty-response-sentinel",
        },
        max_iterations=2,
        parse_valid=True,
        logical_attribution_integrity=True,
        attempts=[
            {"http_status": 200, "transport_error_type": None},
            {"http_status": 200, "transport_error_type": None},
        ],
        physical_sends=2,
        unexpected_outbound_blocks=0,
        provider_budget_blocks=0,
        attribution_mismatch_blocks=0,
    )
    assert decision.effective_completed is True
    assert decision.hermes_completed is False
    assert decision.terminal_iteration_override_used is True
    assert decision.reason == "valid_terminal_iteration_response"
