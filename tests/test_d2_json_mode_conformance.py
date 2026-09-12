from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import d2_json_mode_contract as contract  # noqa: E402
import d2_json_mode_runtime as runtime  # noqa: E402
from resonance_world import d2_terminal_adapter as adapter  # noqa: E402


def _valid_payload() -> dict[str, object]:
    return {"actions": list(adapter.ACTIONS) * 2, "strategy": "bounded-ascii"}


def test_exact_adapter_blob_and_request_intervention_are_frozen() -> None:
    probes = contract.validate_frozen_contract()
    assert len(probes) == 72
    assert contract.git_blob_sha(contract.ADAPTER_PATH) == (
        "ba16d2eb4b7255437c8ab224e91d5ed093897990"
    )
    assert runtime.request_overrides(7) == {
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
        "extra_body": {"thinking": {"type": "disabled"}},
        "extra_headers": {"X-Resonance-World-Logical-Index": "7"},
    }


def test_probe_balance_and_freshness() -> None:
    probes = contract.load_probes()
    assert [row["logical_index"] for row in probes] == list(range(72))
    assert len({row["probe_id"] for row in probes}) == 72
    assert len({row["seed"] for row in probes}) == 72
    assert min(row["seed"] for row in probes) >= 4_000_000
    assert Counter(row["call_shape"] for row in probes) == Counter(
        {
            "fresh_evaluation": 18,
            "developed_development": 18,
            "developed_evaluation": 18,
            "oracle_evaluation": 18,
        }
    )
    for shape in ("developed_development", "developed_evaluation"):
        rows = [row for row in probes if row["call_shape"] == shape]
        assert Counter(row["development_budget"] for row in rows) == Counter(
            {40: 6, 80: 6, 160: 6}
        )


def test_no_provider_derived_strategy_propagation() -> None:
    probes = contract.load_probes()
    developed = [row for row in probes if row["call_shape"].startswith("developed_")]
    prompts = [contract.user_prompt(row) for row in developed]
    assert all("never provider-derived" in prompt for prompt in prompts)
    assert all("json-mode conformance engineering sentinel only" in prompt for prompt in prompts)


def test_exact_parser_acceptance_is_not_relaxed() -> None:
    valid = json.dumps(_valid_payload(), separators=(",", ":"))
    assert adapter.parse_response(valid)[0] is True
    assert adapter.parse_response("```json\n" + valid + "\n```")[0] is False
    assert adapter.parse_response(valid + "\ntrailing")[0] is False
    payload = _valid_payload()
    payload["extra"] = True
    assert adapter.parse_response(json.dumps(payload))[0] is False
    payload = _valid_payload()
    payload["actions"] = ["KAPPA"] * 7
    assert adapter.parse_response(json.dumps(payload))[0] is False


def test_bounded_parse_diagnostics_do_not_change_acceptance() -> None:
    valid = json.dumps(_valid_payload())
    assert contract.parse_diagnostic(valid) == "valid"
    assert contract.parse_diagnostic("not-json") == "json_decode_failure"
    assert contract.parse_diagnostic("[]") == "non_object_top_level"
    assert contract.parse_diagnostic('{"actions":[],"other":1}') == "extra_keys"
    assert contract.parse_diagnostic('{"actions":"KAPPA"}') == "actions_not_list"
    assert contract.parse_diagnostic('{"actions":["KAPPA"]}') == "wrong_action_count"
    bad = {"actions": ["KAPPA"] * 7 + ["NOPE"]}
    assert contract.parse_diagnostic(json.dumps(bad)) == "invalid_action"
    bad = _valid_payload()
    bad["strategy"] = 3
    assert contract.parse_diagnostic(json.dumps(bad)) == "strategy_not_string"
    bad = _valid_payload()
    bad["strategy"] = "x" * (adapter.MAX_STRATEGY_CHARS + 1)
    assert contract.parse_diagnostic(json.dumps(bad)) == "strategy_too_long"
    bad = _valid_payload()
    bad["strategy"] = "é"
    assert contract.parse_diagnostic(json.dumps(bad)) == "strategy_non_ascii"


def test_preflight_is_zero_provider_and_marker_absent() -> None:
    result = runtime.preflight()
    assert result["provider_execution_performed"] is False
    assert result["execution_marker_absent"] is True
    assert result["probe_count"] == 72
    assert result["request_intervention"] == {
        "response_format": {"type": "json_object"}
    }
    assert result["terminal_adapter_git_blob_sha"] == (
        "ba16d2eb4b7255437c8ab224e91d5ed093897990"
    )
