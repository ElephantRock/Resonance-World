from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import d2_json_mode_agent as agent  # noqa: E402
import d2_json_mode_contract as contract  # noqa: E402

from resonance_world import d2_terminal_adapter as exact_adapter  # noqa: E402
from resonance_world import d2_top_level_projection as projection  # noqa: E402


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
    assert min(row["seed"] for row in rows) >= 4_100_000


def test_exact_valid_response_does_not_exercise_projection() -> None:
    text = _valid_payload()
    exact_valid, _ = exact_adapter.parse_response(text)
    result = projection.parse_projected_response(text)
    assert exact_valid is True
    assert result.valid is True
    assert result.exact_parse_valid is True
    assert result.projection_used is False
    assert result.unknown_key_count == 0
    assert result.diagnostic == "exact_valid"


def test_unknown_top_level_key_is_projected_and_fingerprinted() -> None:
    text = _valid_payload(note="ignore-me")
    exact_valid, _ = exact_adapter.parse_response(text)
    result = projection.parse_projected_response(text)
    assert exact_valid is False
    assert result.valid is True
    assert result.exact_parse_valid is False
    assert result.projection_used is True
    assert result.unknown_key_count == 1
    assert len(result.unknown_key_fingerprints) == 1
    assert len(result.unknown_key_fingerprints[0]) == 64
    assert "note" not in result.unknown_key_fingerprints
    assert result.diagnostic == "unknown_top_level_keys_projected"


def test_projection_does_not_repair_required_semantics() -> None:
    text = json.dumps(
        {
            "actions": ["KAPPA"] * 7,
            "strategy": "bounded",
            "note": "ignore-me",
        }
    )
    result = projection.parse_projected_response(text)
    assert result.valid is False
    assert result.projection_used is True
    assert result.unknown_key_count == 1
    assert result.diagnostic == "wrong_action_count"


def test_projection_does_not_extract_or_repair_json() -> None:
    fenced = '```json\n' + _valid_payload(note="x") + '\n```'
    embedded = "prefix " + _valid_payload(note="x")
    assert projection.parse_projected_response(fenced).valid is False
    assert projection.parse_projected_response(embedded).valid is False


def test_projection_preserves_strategy_bounds() -> None:
    result = projection.parse_projected_response(
        _valid_payload(strategy="x" * (exact_adapter.MAX_STRATEGY_CHARS + 1), note="x")
    )
    assert result.valid is False
    assert result.diagnostic == "strategy_too_long"


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
    assert first["issue"] == 263
    assert first["probe_count"] == 72


def test_terminal_adapter_semantics_remain_unchanged_for_projected_validity() -> None:
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


def test_system_prompt_still_requests_no_extra_keys() -> None:
    prompt = contract.system_prompt()
    assert "Do not include other keys" in prompt
