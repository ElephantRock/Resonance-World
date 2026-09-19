from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import d2_vnext_s2_acquisition_core as core
import d2_vnext_s2_hermes_client as client
import materialize_d2_vnext_s2_source_acquisition as materializer
from resonance_world import d2_terminal_adapter

ROOT = Path(__file__).resolve().parents[1]


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def test_fresh_namespace_and_seed_bases_are_frozen() -> None:
    assert core.NAMESPACE == "rw.d2-vnext-s2-source-acquisition.v1"
    assert core.SCHEMA_SEED_BASES == {
        "threshold_at_4": 10_000_000,
        "parity_pair": 10_200_000,
        "interval_pair": 10_400_000,
        "pairwise_order": 10_600_000,
    }
    assert [core.schema_and_local_index(i * 96)[0] for i in range(4)] == list(
        core.SCHEMA_ORDER
    )


def test_fresh_cohort_has_no_predecessor_overlap() -> None:
    lock = materializer.build_cohort_lock()
    assert lock["pair_count"] == 384
    assert lock["pairs_per_schema"] == 96
    assert lock["fresh_namespace"] == core.NAMESPACE
    assert lock["cross_schema_seed_overlap"] == 0
    assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())
    assert lock["all_development_evaluation_overlaps_zero"] is True
    assert lock["production_historical_substrate_enabled"] is False


def test_materialization_is_deterministic() -> None:
    assert materializer.build_cohort_lock() == materializer.build_cohort_lock()
    assert materializer.build_shard_map() == materializer.build_shard_map()
    shard_map = materializer.build_shard_map()
    assert shard_map["shard_count"] == 24
    assert shard_map["pairs_per_provider_shard"] == 16
    assert shard_map["registered_logical_calls_if_all_pairs_complete"] == 21_120
    assert shard_map["maximum_physical_provider_sends_per_logical_call"] == 36
    assert shard_map["maximum_physical_provider_sends_per_shard"] == 2_000
    assert shard_map["maximum_physical_provider_sends_campaign"] == 48_000
    assert shard_map["minimum_analyzable_pairs_per_schema"] == 88
    assert shard_map["favorable_result_possible_with_missing_whole_shard"] is False


def test_exact_qualified_transport_primitives_are_restored() -> None:
    assert _git_blob_sha(ROOT / "src/resonance_world/d2_terminal_adapter.py") == (
        "ba16d2eb4b7255437c8ab224e91d5ed093897990"
    )
    assert _git_blob_sha(ROOT / "src/resonance_world/provider_send_guard.py") == (
        "4b8896235d8048523d007400d0acfe85470f628c"
    )


def test_scientific_structured_prompt_is_noncopyable_and_exact() -> None:
    prompt = client.SYSTEM_PROMPT
    required = (
        "JSON square-bracket array of exactly 8 strings",
        "Never return actions as an object, map, string, keyed per-case record, or scalar",
        '{"actions":["<ACTION_1>","<ACTION_2>","<ACTION_3>","<ACTION_4>","<ACTION_5>","<ACTION_6>","<ACTION_7>","<ACTION_8>"]}',
        "never emit placeholder text",
        "silently verify: valid JSON object",
    )
    assert all(fragment in prompt for fragment in required)
    assert client.FORBIDDEN_EXEMPLAR not in prompt
    assert d2_terminal_adapter.parse_response(
        '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}'
    )[0]


def test_exact_parser_diagnostics() -> None:
    assert client.bounded_parse_diagnostic("not-json") == "json_decode_failure"
    assert client.bounded_parse_diagnostic("[]") == "top_level_not_object"
    assert client.bounded_parse_diagnostic('{"actions":[],"x":1}') == "extra_keys"
    assert client.bounded_parse_diagnostic('{"strategy":"x"}') == "actions_missing"
    assert client.bounded_parse_diagnostic('{"actions":{}}') == "actions_not_list"
    assert client.bounded_parse_diagnostic('{"actions":["KAPPA"]}') == "wrong_action_count"
    valid = '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}'
    assert client.bounded_parse_diagnostic(valid) == "exact_valid"


def test_retry_prompt_contains_only_original_request_and_bounded_diagnostic() -> None:
    original = "ORIGINAL-SCIENTIFIC-USER-PROMPT"
    retry = client.retry_user_prompt(original, "extra_keys")
    assert original in retry
    assert "extra_keys" in retry
    assert "Raw prior response content is not provided" in retry
    assert "must not be inferred, reconstructed, or repaired" in retry
    with pytest.raises(ValueError):
        client.retry_user_prompt(original, "exact_valid")


def _first(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "runtime_exception": False,
        "final_response_length": 10,
        "exact_structured_parse_valid": False,
        "exact_attributed_clean_transport": True,
        "logical_attribution_integrity": True,
        "hermes_completed_flag_valid": True,
        "hermes_failed": False,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "json_mode_compatibility_failure": False,
    }
    row.update(overrides)
    return row


class _Budget:
    blocked_unexpected = 0
    blocked_budget = 0


class _Ledger:
    attribution_mismatches = 0


def test_retry_eligibility_is_fail_closed() -> None:
    assert client.retry_eligible(_first(), _Budget(), _Ledger())
    for key, value in (
        ("runtime_exception", True),
        ("final_response_length", 0),
        ("exact_structured_parse_valid", True),
        ("exact_attributed_clean_transport", False),
        ("logical_attribution_integrity", False),
        ("hermes_completed_flag_valid", False),
        ("hermes_failed", True),
        ("hermes_partial", True),
        ("hermes_interrupted", True),
        ("hermes_error_present", True),
        ("json_mode_compatibility_failure", True),
    ):
        assert not client.retry_eligible(_first(**{key: value}), _Budget(), _Ledger())


def test_json_mode_compatibility_statuses_are_exact() -> None:
    assert client.COMPATIBILITY_STATUSES == frozenset({400, 404, 409, 415, 422})
    assert not ({408, 429, 500, 502, 503, 504} & client.COMPATIBILITY_STATUSES)


def test_provider_caps_and_agent_profile_are_frozen() -> None:
    assert client.MODEL == "glm-5.3"
    assert client.MAX_ITERATIONS == 2
    assert client.MAX_AGENT_INVOCATIONS == 2
    assert client.MAX_TOKENS == 768
    assert client.TEMPERATURE == 0.8
    assert client.MAX_LOGICAL_CALLS_PER_SHARD == 880
    assert client.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL == 36
    assert client.MAX_PHYSICAL_SENDS_PER_SHARD == 2000
    plan = json.loads(
        (ROOT / "research/d2_vnext_s2/D2_VNEXT_S2_REQUEST_PLAN.json").read_text()
    )
    assert plan["max_physical_provider_sends_campaign"] == 48_000
    assert plan["scientific_campaign_authorized"] is False
    assert plan["provider_execution_authorized"] is False
    assert plan["same_request_stream_rerun_allowed"] is False
    assert plan["acceptance_action_authorized"] is False
    assert plan["historical_substrate_enabled"] is False


def test_execution_marker_is_absent_from_construction_candidate() -> None:
    assert not (ROOT / "research/d2_vnext_s2/RUN_D2_VNEXT_S2_SOURCE_ACQUISITION").exists()
