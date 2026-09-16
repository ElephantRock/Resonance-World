from __future__ import annotations

import inspect
from contextlib import contextmanager

import d2_format_regeneration_contract as contract
import d2_format_regeneration_probe as probe_mod
import d2_format_regeneration_runtime as runtime
from resonance_world import d2_terminal_adapter as adapter


def _attempt(status: int = 200, *, transport_error_type: str | None = None) -> dict[str, object]:
    return {
        "origin_logical_index": 0,
        "logical_index": 0,
        "logical_send_index": 1,
        "total_send_index": 1,
        "http_status": status,
        "transport_error_type": transport_error_type,
    }


def _inv(*, valid: bool, length: int = 20, clean: bool = True, failed: bool = False, diagnostic: str | None = None) -> dict[str, object]:
    diag = "exact_valid" if valid else (diagnostic or "json_decode_failure")
    return {
        "runtime_exception": False,
        "hermes_completed_flag_valid": True,
        "hermes_completed": valid,
        "hermes_failed": failed,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "api_calls": 1,
        "result_api_calls": 1,
        "final_response_length": length,
        "final_response_sha256": "a" * 64 if length else None,
        "exact_structured_parse_valid": valid,
        "structured_parse_valid": valid,
        "parse_diagnostic": diag,
        "placeholder_leak": False,
        "strategy_length": 0,
        "strategy_sha256": None,
        "physical_provider_sends_observed": 1,
        "attempts": [_attempt()] if clean else [_attempt(500)],
        "logical_attribution_integrity": True,
        "exact_attributed_clean_transport": clean,
        "json_mode_compatibility_failure": False,
        "effective_completed": valid,
        "terminal_iteration_override_used": False,
        "adapter_reason": "hermes_completed" if valid else "structured_parse_invalid",
    }


class _Budget:
    blocked_unexpected = 0
    blocked_budget = 0

    def __init__(self) -> None:
        self.sends = 0

    @contextmanager
    def logical_call(self, logical: int):
        del logical
        yield

    def sends_for_logical_call(self, logical: int) -> int:
        del logical
        return self.sends


class _Ledger:
    attribution_mismatches = 0

    def __init__(self) -> None:
        self._rows: list[dict[str, object]] = []

    def rows(self, logical: int) -> list[dict[str, object]]:
        del logical
        return list(self._rows)


def test_frozen_contract_and_fresh_probe_balance() -> None:
    rows = contract.validate_frozen_contract()
    assert len(rows) == 72
    assert rows[0]["seed"] == 4_500_001
    assert rows[-1]["seed"] == 4_500_072
    assert len({row["probe_id"] for row in rows}) == 72
    assert len({row["seed"] for row in rows}) == 72


def test_primary_prompt_is_exact_prior_json_skeleton_contract() -> None:
    prompt = contract.system_prompt()
    assert contract.sha(prompt) == "92ba97ccc1e5aec273114785d0d8a5c533ba46a6340d7c74f9fc085efe516c6e"
    assert '{"actions":["<ACTION_1>","<ACTION_2>","<ACTION_3>","<ACTION_4>","<ACTION_5>","<ACTION_6>","<ACTION_7>","<ACTION_8>"]}' in prompt
    assert '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}' not in prompt


def test_retry_prompt_uses_only_bounded_diagnostic_not_raw_response() -> None:
    row = contract.load_probes()[0]
    raw = 'RAW-FIRST-RESPONSE-SHOULD-NEVER-PROPAGATE'
    text = contract.retry_user_prompt(row, "json_decode_failure")
    assert "json_decode_failure" in text
    assert "Raw prior response content is not provided" in text
    assert raw not in text
    assert list(inspect.signature(contract.retry_user_prompt).parameters) == ["probe", "diagnostic"]


def test_exact_parser_and_bounded_diagnostics_are_unchanged() -> None:
    good = '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}'
    bad_extra = '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"],"x":1}'
    bad_object = '{"actions":{"0":"KAPPA"}}'
    assert adapter.parse_response(good)[0] is True
    assert contract.bounded_parse_diagnostic(good) == "exact_valid"
    assert adapter.parse_response(bad_extra)[0] is False
    assert contract.bounded_parse_diagnostic(bad_extra) == "extra_keys"
    assert adapter.parse_response(bad_object)[0] is False
    assert contract.bounded_parse_diagnostic(bad_object) == "actions_not_list"


def test_retry_eligibility_is_exact_and_fail_closed() -> None:
    budget = _Budget()
    ledger = _Ledger()
    first = _inv(valid=False)
    assert probe_mod.retry_eligible(first, budget, ledger) is True
    for mutation in (
        {"final_response_length": 0},
        {"exact_structured_parse_valid": True},
        {"exact_attributed_clean_transport": False},
        {"logical_attribution_integrity": False},
        {"hermes_failed": True},
        {"hermes_partial": True},
        {"hermes_interrupted": True},
        {"hermes_error_present": True},
        {"json_mode_compatibility_failure": True},
        {"runtime_exception": True},
    ):
        row = dict(first)
        row.update(mutation)
        assert probe_mod.retry_eligible(row, budget, ledger) is False


def test_json_mode_compatibility_status_set_excludes_transients() -> None:
    for status in (400, 404, 409, 415, 422):
        row = _inv(valid=False, length=0)
        row["runtime_exception"] = True
        row["attempts"] = [_attempt(status)]
        assert probe_mod._compatibility_failure(row) is True
    for status in (408, 429, 500, 502, 503):
        row = _inv(valid=False, length=0)
        row["runtime_exception"] = True
        row["attempts"] = [_attempt(status)]
        assert probe_mod._compatibility_failure(row) is False


def test_outcome_precedence() -> None:
    kwargs = dict(apparatus=False, compatibility=0, exact_invalid=0, attempted=72, effective=72, base_pass=True)
    assert runtime.classify_outcome(**kwargs) == "PASS"
    assert runtime.classify_outcome(**{**kwargs, "effective": 71, "base_pass": False}) == "FAIL_COMPLETION"
    assert runtime.classify_outcome(**{**kwargs, "exact_invalid": 1, "effective": 71, "base_pass": False}) == "FAIL_STRUCTURED_CONTRACT"
    assert runtime.classify_outcome(**{**kwargs, "compatibility": 1, "exact_invalid": 1, "base_pass": False}) == "FAIL_JSON_MODE_COMPATIBILITY"
    assert runtime.classify_outcome(**{**kwargs, "apparatus": True, "compatibility": 1, "exact_invalid": 1, "base_pass": False}) == "APPARATUS_FAILURE"


def test_run_probe_valid_first_never_retries(monkeypatch) -> None:
    budget = _Budget()
    ledger = _Ledger()
    calls = []

    def fake_invoke(logical, prompt, budget_arg, ledger_arg):
        del logical, prompt, budget_arg
        calls.append(1)
        ledger_arg._rows.append(_attempt())
        budget.sends += 1
        return _inv(valid=True)

    monkeypatch.setattr(probe_mod, "_invoke", fake_invoke)
    row = probe_mod.run_probe(budget, ledger, contract.load_probes()[0])
    assert len(calls) == 1
    assert row["retry_used"] is False
    assert row["accepted_attempt_index"] == 1
    assert row["agent_invocation_count"] == 1


def test_run_probe_clean_invalid_gets_exactly_one_retry(monkeypatch) -> None:
    budget = _Budget()
    ledger = _Ledger()
    calls = []

    def fake_invoke(logical, prompt, budget_arg, ledger_arg):
        del logical, budget_arg
        calls.append(prompt)
        ledger_arg._rows.append(_attempt())
        budget.sends += 1
        return _inv(valid=False) if len(calls) == 1 else _inv(valid=True)

    monkeypatch.setattr(probe_mod, "_invoke", fake_invoke)
    row = probe_mod.run_probe(budget, ledger, contract.load_probes()[0])
    assert len(calls) == 2
    assert row["retry_used"] is True
    assert row["accepted_attempt_index"] == 2
    assert row["agent_invocation_count"] == 2
    assert "json_decode_failure" in calls[1]
    assert row["retry_raw_first_response_content_included"] is False


def test_run_probe_invalid_retry_stops_after_two_invocations(monkeypatch) -> None:
    budget = _Budget()
    ledger = _Ledger()
    calls = []

    def fake_invoke(logical, prompt, budget_arg, ledger_arg):
        del logical, prompt, budget_arg
        calls.append(1)
        ledger_arg._rows.append(_attempt())
        budget.sends += 1
        return _inv(valid=False)

    monkeypatch.setattr(probe_mod, "_invoke", fake_invoke)
    row = probe_mod.run_probe(budget, ledger, contract.load_probes()[0])
    assert len(calls) == 2
    assert row["agent_invocation_count"] == 2
    assert row["accepted_attempt_index"] is None
    assert row["exact_structured_parse_valid"] is False
    assert row["retry_policy_violation"] is False
