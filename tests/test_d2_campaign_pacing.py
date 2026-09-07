from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
RESEARCH = ROOT / "research" / "d2_campaign_pacing"
sys.path.insert(0, str(SCRIPTS))

import qualify_d2_campaign_pacing as runner  # noqa: E402


def load_plan() -> dict:
    return json.loads((RESEARCH / "PACING_REQUEST_PLAN.json").read_text())


def test_request_plan_is_engineering_only_and_bounded() -> None:
    plan = load_plan()
    assert plan["schema"] == "d2-campaign-pacing-request-plan-v0.1"
    assert plan["issue"] == 210
    assert plan["engineering_only"] is True
    assert plan["endpoint"] == "https://api.z.ai/api/paas/v4/chat/completions"
    assert plan["model"] == "glm-5-turbo"
    assert plan["request_count_maximum"] == 31
    assert plan["max_attempts_per_logical_call"] == 1
    assert plan["redirect_policy"] == "reject_do_not_follow"
    assert plan["global_request_start_gate"] is True
    assert plan["historical_failed_burst_schedule_reproduced"] is False
    assert plan["historical_d2d_s2_max_parallel_shards"] == 4
    assert plan["historical_d2d_s2_per_client_minimum_interval_seconds"] == 0.35
    assert plan["provider_execution_authorized"] is False
    assert plan["same_request_stream_rerun_allowed"] is False
    assert plan["scientific_campaign_authorized"] is False
    assert plan["scientific_scoring_performed"] is False
    assert plan["registry_promotion_authorized"] is False
    assert plan["historical_substrate_enabled"] is False


def test_frozen_profiles_match_runner_and_historical_diagnostic_is_last() -> None:
    plan = load_plan()
    assert plan["profiles"] == [dict(row) for row in runner.PROFILES]
    assert [row["id"] for row in plan["profiles"]] == [
        "baseline_serial_5s",
        "serial_2s",
        "serial_1s",
        "concurrency2_1s",
        "concurrency4_035s",
    ]
    assert plan["profiles"][-1]["max_concurrency"] == 4
    assert plan["profiles"][-1]["minimum_start_interval_seconds"] == 0.35
    assert sum(row["calls"] for row in plan["profiles"]) == 31


def test_representative_request_is_deterministic_and_non_scientific() -> None:
    first = runner.representative_body()
    second = runner.representative_body()
    assert first == second
    encoded = runner.canonical_bytes(first)
    materialized = runner.materialized_plan()
    assert materialized["request_body_sha256"] == runner.sha256_bytes(encoded)
    assert materialized["request_body_bytes"] == len(encoded)
    assert materialized["request_count_maximum"] == 31
    user = first["messages"][1]["content"]
    assert "ENGINEERING ONLY" in user
    assert "not a registered scientific task" in user
    assert "Return KAPPA for every case" in user
    assert first["max_tokens"] == 768
    assert first["response_format"] == {"type": "json_object"}


def test_recommendation_stops_at_first_failed_profile() -> None:
    rows = [
        {"profile_id": "p0", "profile_pass": True},
        {"profile_id": "p1", "profile_pass": True},
        {"profile_id": "p2", "profile_pass": False},
        {"profile_id": "p3", "profile_pass": True},
    ]
    assert runner.recommended_profile(rows) == "p1"
    assert runner.recommended_profile([{**rows[0], "profile_pass": False}]) is None
    assert runner.recommended_profile(rows[:2]) == "p1"


def test_marker_parser_is_strict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "marker"
    monkeypatch.setattr(runner, "MARKER_PATH", marker)
    marker.write_text(
        "candidate_sha=" + "a" * 40 + "\n"
        "issue=210\n"
        "authorization=D2_campaign_pacing_execution_explicitly_authorized\n"
    )
    assert runner.marker_record()["candidate_sha"] == "a" * 40
    marker.write_text(
        "candidate_sha=" + "a" * 40 + "\n"
        "issue=999\n"
        "authorization=D2_campaign_pacing_execution_explicitly_authorized\n"
    )
    with pytest.raises(RuntimeError, match="issue"):
        runner.marker_record()


def test_execute_fails_closed_without_explicit_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(runner.AUTH_ENV, raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        runner.execute()


def test_result_authority_cannot_promote_registry() -> None:
    registry = json.loads((ROOT / "research" / "mechanisms" / "registry.json").read_text())
    node = next(
        row
        for row in registry["nodes"]
        if row.get("mechanism_id") == "d2_stochastic_capability_reproduction"
    )
    assert node["status"] == "internally_replicated"
    assert node.get("production_historical_substrate_enabled") is False
    plan = load_plan()
    assert plan["registry_promotion_authorized"] is False
    assert plan["historical_substrate_enabled"] is False
