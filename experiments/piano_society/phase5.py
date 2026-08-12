"""Preregistered analysis for PIANO Phase-5 institutional memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from experiments.piano_society.phase3 import config_digest

_EXPERIMENT = "piano-society-runtime-v0-phase5-institutional-memory"
_REVISION = "glm5.2-institutional-memory-v1"
_FIELD_SHA = "e877bf03dbf6681ce7cbd98d984e73c032e911aa"
_MODEL = "glm-5.2"
_PHASE4C_SHA = "b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1"
_PHASE4C_ARTIFACT = (
    "sha256:465c5d07c7e98a33dccedf24c0fb504a82ad54632590ec1fce8eddd1cf57279e"
)
_SOURCE_RUN = 31641437682
_SOURCE_SHA = "6ed54f7d432a090ccaf58c720a6bd375a08b30af"
_SOURCE_ARTIFACT = (
    "sha256:f055667945b1cd1a430e1a83f4e0fd933e1438db1fed45392bf4384209628ffe"
)
_CAPSULE_SHA = "c41c50165c0fb93d49848bb44b0fcd58172402fa52f7f05fd5f3456222b78c0d"
_CANDIDATE_SHA = "49f1830454677be49457e908a832769b9119d02e83f9c7bf9d45d776530b50c1"
_SEARCH_ARTIFACT = (
    "sha256:d952c7ed7140cf016eb2a37d495f0d386066f06946a1501ce24eb44a5e27dfb7"
)
_ARMS = ("memory_reset", "memory_retained")
_STRATEGIES = ("specialist", "balanced")
_PAYLOAD_SCHEMA = "resonance-world-piano-phase5-memory-arm-v0.1"
_RECORD_SCHEMA = "resonance-world-piano-phase5-memory-unit-v0.1"
_REAL_SKILLS = (
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
)
_EXPECTED_FIELDS = (
    "w4-source-seed-12227",
    "w4-source-seed-12329",
    "w4-source-seed-12433",
    "w4-source-seed-12539",
    "w4-source-seed-12641",
    "w4-source-seed-12743",
)
_EXPECTED_MISSIONS = (
    ("route-a", "public_health", "mobility", "balanced", "skill-e", "skill-f"),
    ("route-b", "water_systems", "urban_heat", "balanced", "skill-b", "skill-a"),
    ("route-c", "public_health", "supply_networks", "specialist", "skill-e", "skill-d"),
    ("route-d", "supply_networks", "public_health", "specialist", "skill-d", "skill-e"),
)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    return value


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def materialize_units(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = _mapping(config.get("source_lock"), "source_lock")
    fields = tuple(str(item) for item in _sequence(source.get("confirmatory_fields"), "fields"))
    if fields != _EXPECTED_FIELDS:
        raise ValueError("Phase-5 confirmatory field set/order differs from lock")
    raw_missions = _sequence(config.get("missions"), "missions")
    missions: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_missions):
        row = _mapping(raw, "mission")
        expected = _EXPECTED_MISSIONS[index] if index < len(_EXPECTED_MISSIONS) else None
        observed = (
            row.get("mission_id"),
            row.get("lead_skill"),
            row.get("support_skill"),
            row.get("hidden_regime"),
            row.get("public_lead_skill"),
            row.get("public_support_skill"),
        )
        if expected is None or observed != expected or row.get("context") != expected[0]:
            raise ValueError("Phase-5 selected mission set differs from mission-search lock")
        missions.append(dict(row))
    if len(missions) != 4:
        raise ValueError("Phase-5 requires exactly four selected missions")

    units: list[dict[str, Any]] = []
    strategy_counts: Counter[str] = Counter()
    arm_counts: Counter[str] = Counter()
    cross_counts: Counter[tuple[str, str]] = Counter()
    for field_index, field_id in enumerate(fields):
        for mission_index, mission in enumerate(missions):
            specialist_first = (field_index + mission_index) % 2 == 0
            strategy_order = (
                ("specialist", "balanced")
                if specialist_first
                else ("balanced", "specialist")
            )
            strategy_label = "specialist_first" if specialist_first else "balanced_first"
            retained_first = field_index % 2 == 0
            arm_order = (
                ("memory_retained", "memory_reset")
                if retained_first
                else ("memory_reset", "memory_retained")
            )
            arm_label = "memory_retained_first" if retained_first else "memory_reset_first"
            unit_id = f"{field_id}::{mission['mission_id']}"
            units.append(
                {
                    "unit_id": unit_id,
                    "field_id": field_id,
                    "field_index": field_index,
                    "mission_index": mission_index,
                    "mission": mission,
                    "trial_seed": 950000 + field_index * 100 + mission_index,
                    "strategy_order": strategy_order,
                    "strategy_order_label": strategy_label,
                    "arm_order": arm_order,
                    "arm_order_label": arm_label,
                }
            )
            strategy_counts[strategy_label] += 1
            arm_counts[arm_label] += 1
            cross_counts[(strategy_label, arm_label)] += 1
    if len(units) != 24:
        raise ValueError("Phase-5 requires exactly 24 paired units")
    if strategy_counts != Counter({"specialist_first": 12, "balanced_first": 12}):
        raise ValueError("Phase-5 strategy presentation is not exactly 12/12")
    if arm_counts != Counter({"memory_retained_first": 12, "memory_reset_first": 12}):
        raise ValueError("Phase-5 arm order is not exactly 12/12")
    if len(cross_counts) != 4 or any(count != 6 for count in cross_counts.values()):
        raise ValueError("Phase-5 presentation/arm order must cross-balance six each")
    return units


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _EXPERIMENT:
        raise ValueError("unsupported Phase-5 experiment identifier")
    if config.get("preregistration_revision") != _REVISION:
        raise ValueError("unexpected Phase-5 preregistration revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-5 campaign must be locked")
    if config.get("field_revision") != _FIELD_SHA:
        raise ValueError("Phase-5 Field revision differs from lock")
    if config.get("required_model_snapshot") != _MODEL:
        raise ValueError("Phase-5 model differs from lock")

    prerequisite = _mapping(config.get("validated_prerequisites"), "validated_prerequisites")
    expected_prerequisite = {
        "phase4c_world_revision": _PHASE4C_SHA,
        "phase4c_workflow_run": 31638087507,
        "phase4c_artifact_id": 9158432521,
        "phase4c_artifact_digest": _PHASE4C_ARTIFACT,
        "phase4c_advance_to_phase5": True,
        "phase4c_role_failure_delta": -0.48333333333333334,
        "phase4c_spoof_capture_delta": -0.48333333333333334,
    }
    if dict(prerequisite) != expected_prerequisite:
        raise ValueError("Phase-5 Phase-4C prerequisite binding differs from lock")

    source = _mapping(config.get("source_lock"), "source_lock")
    expected_source = {
        "workflow_run": _SOURCE_RUN,
        "world_revision": _SOURCE_SHA,
        "artifact_id": 9159028914,
        "artifact_name": "piano-society-phase5-frozen-source",
        "artifact_digest": _SOURCE_ARTIFACT,
        "capsule_sha256": _CAPSULE_SHA,
        "candidate_sha256": _CANDIDATE_SHA,
        "field_count": 8,
        "agent_count": 96,
        "calibration_fields": ["w4-source-seed-12017", "w4-source-seed-12119"],
        "confirmatory_fields": list(_EXPECTED_FIELDS),
    }
    if dict(source) != expected_source:
        raise ValueError("Phase-5 exact frozen-source binding differs from lock")

    search = _mapping(config.get("mission_search_lock"), "mission_search_lock")
    expected_search = {
        "artifact_id": 9159035534,
        "artifact_name": "piano-society-phase5-mission-search",
        "artifact_digest": _SEARCH_ARTIFACT,
        "revision": "piano-phase5-mission-search-v1",
        "model_calls": 0,
        "candidate_count": 60,
        "selected_unit_count": 8,
        "mean_selected_historical_best_lift_over_binary_mean": 0.04150390625,
        "nonnegative_selected_units": 8,
        "accepted": True,
    }
    if dict(search) != expected_search:
        raise ValueError("Phase-5 mission-search prerequisite binding differs from lock")

    backend = _mapping(config.get("model_backend"), "model_backend")
    expected_backend = {
        "provider": "zai",
        "endpoint": "coding_chat_completions",
        "base_url": "https://api.z.ai/api/coding/paas/v4",
        "thinking": "disabled",
        "do_sample": False,
        "temperature": 0.0,
        "provider_seed_supported": False,
        "retry_timeout": True,
        "retry_contract_errors": True,
        "contract_retry_prompt_hardening": True,
        "unique_request_id_per_attempt": True,
        "timeout_seconds": 60.0,
        "max_attempts": 12,
        "retry_backoff_cap_seconds": 30.0,
        "max_workers": 3,
        "arm_order": "retained_first_when_field_index_even_else_reset_first",
        "strategy_order": (
            "specialist_first_when_field_index_plus_mission_index_even_else_balanced_first"
        ),
    }
    if dict(backend) != expected_backend:
        raise ValueError("Phase-5 provider transport differs from lock")

    memory = _mapping(config.get("institutional_memory"), "institutional_memory")
    expected_memory = {
        "formation_depth": 48,
        "formation_strategy_order": ["specialist", "balanced"],
        "turnover_fraction": 1.0,
        "evaluation_updates_memory": False,
        "model_visible_memory": "current_context_raw_attempts_successes_rates_only",
        "model_visible_last_successful_pair": False,
        "model_visible_historical_best_label": False,
        "reset_memory_shape": "same_schema_zero_attempts_zero_successes_null_rates",
        "environment_reads_memory": False,
        "strategy_vocabulary": ["specialist", "balanced"],
        "evaluation_trials_per_unit": 128,
        "grounded_success_threshold": 0.5,
    }
    if dict(memory) != expected_memory:
        raise ValueError("Phase-5 institutional-memory intervention differs from lock")

    aliases = _mapping(config.get("skill_aliases"), "skill_aliases")
    if dict(aliases) != {
        "urban_heat": "skill-a",
        "water_systems": "skill-b",
        "energy_storage": "skill-c",
        "supply_networks": "skill-d",
        "public_health": "skill-e",
        "mobility": "skill-f",
    }:
        raise ValueError("Phase-5 skill aliases differ from lock")
    if tuple(config.get("arms", ())) != _ARMS:
        raise ValueError("Phase-5 arms differ from lock")
    if config.get("confirmatory_field_count") != 6 or config.get("missions_per_field") != 4:
        raise ValueError("Phase-5 field/mission dimensions differ from lock")
    if config.get("required_paired_units") != 24:
        raise ValueError("Phase-5 requires 24 paired units")
    if config.get("calls_per_arm_unit") != 4 or config.get("max_output_tokens_per_call") != 128:
        raise ValueError("Phase-5 model call budget differs from lock")
    if config.get("primary_metric") != "mission_success_rate":
        raise ValueError("Phase-5 primary metric differs from lock")
    if config.get("strategy_order_counts") != {
        "specialist_first": 12,
        "balanced_first": 12,
    }:
        raise ValueError("Phase-5 strategy-order count lock differs")
    if config.get("arm_order_counts") != {
        "memory_retained_first": 12,
        "memory_reset_first": 12,
    }:
        raise ValueError("Phase-5 arm-order count lock differs")
    if config.get("presentation_arm_cross_count_each") != 6:
        raise ValueError("Phase-5 presentation/arm cross lock differs")

    gate = _mapping(config.get("advancement_gate"), "advancement_gate")
    expected_gate = {
        "min_mean_retained_minus_reset_success_rate": 0.03,
        "max_primary_sign_test_p": 0.05,
        "min_nonnegative_field_effects": 4,
        "max_outcome_report_mismatch_delta": 0.05,
    }
    if dict(gate) != expected_gate:
        raise ValueError("Phase-5 advancement gate differs from lock")

    units = materialize_units(config)
    return {
        "field_revision": _FIELD_SHA,
        "model_snapshot": _MODEL,
        "source_capsule_sha256": _CAPSULE_SHA,
        "units": units,
        "unit_map": {unit["unit_id"]: unit for unit in units},
        "gate": gate,
        "config_digest": config_digest(config),
    }


def _memory_stats(record: Mapping[str, Any]) -> Mapping[str, Any]:
    audit = _mapping(record.get("audit"), "audit")
    stats = _mapping(audit.get("historical_strategy_stats"), "historical_strategy_stats")
    if set(stats) != set(_STRATEGIES):
        raise ValueError("historical strategy stats must contain specialist/balanced only")
    for strategy in _STRATEGIES:
        row = _mapping(stats[strategy], f"historical_strategy_stats.{strategy}")
        attempts = row.get("attempts")
        successes = row.get("successes")
        rate = row.get("rate")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts <= 0:
            raise ValueError("historical attempts must be positive integers")
        if not isinstance(successes, int) or isinstance(successes, bool):
            raise ValueError("historical successes must be integers")
        if not 0 <= successes <= attempts:
            raise ValueError("historical successes must lie within attempts")
        if not isinstance(rate, (int, float)) or isinstance(rate, bool):
            raise ValueError("historical rate must be numeric")
        if not math.isclose(float(rate), successes / attempts, abs_tol=1e-12):
            raise ValueError("historical rate is inconsistent with attempts/successes")
    return stats


def _historical_best(stats: Mapping[str, Any]) -> str:
    scored: list[tuple[float, int, str]] = []
    for strategy in _STRATEGIES:
        row = _mapping(stats[strategy], strategy)
        scored.append((float(row["rate"]), int(row["attempts"]), strategy))
    return max(scored)[2]


def _validate_model_visible(
    record: Mapping[str, Any],
    *,
    arm: str,
    unit: Mapping[str, Any],
) -> None:
    visible = _mapping(record.get("model_visible"), "model_visible")
    mission_text = visible.get("mission_text")
    roster_text = visible.get("roster_text")
    memory_text = visible.get("memory_text")
    if not all(isinstance(value, str) for value in (mission_text, roster_text, memory_text)):
        raise ValueError("Phase-5 model-visible fields must be strings")
    mission = _mapping(unit["mission"], "mission")
    expected_mission = (
        f"context={mission['context']}; lead_skill={mission['public_lead_skill']}; "
        f"support_skill={mission['public_support_skill']}"
    )
    if mission_text != expected_mission:
        raise ValueError("Phase-5 model-visible mission differs from opaque lock")
    combined = "\n".join((mission_text, roster_text, memory_text)).lower()
    if "hidden_regime" in combined or "regime=" in combined:
        raise ValueError("Phase-5 hidden regime leaked into model-visible context")
    if any(skill.lower() in combined for skill in _REAL_SKILLS):
        raise ValueError("Phase-5 real skill name leaked into model-visible context")
    if "w4-source-seed" in combined or "agent-" in combined:
        raise ValueError("Phase-5 source/agent identifiers leaked into model-visible context")
    try:
        memory_value = json.loads(memory_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Phase-5 memory text must be canonical JSON") from exc
    if not isinstance(memory_value, dict) or set(memory_value) != set(_STRATEGIES):
        raise ValueError("Phase-5 memory text must contain the two binary strategies")
    for strategy in _STRATEGIES:
        row = _mapping(memory_value[strategy], f"memory_text.{strategy}")
        if set(row) != {"attempts", "successes", "rate"}:
            raise ValueError("Phase-5 memory row shape differs from lock")
        if arm == "memory_reset":
            if dict(row) != {"attempts": 0, "successes": 0, "rate": None}:
                raise ValueError("Phase-5 reset memory must be zero/null shaped")
        else:
            audit_row = _mapping(_memory_stats(record)[strategy], strategy)
            expected = {
                "attempts": audit_row["attempts"],
                "successes": audit_row["successes"],
                "rate": audit_row["rate"],
            }
            if dict(row) != expected:
                raise ValueError("Phase-5 retained memory differs from audited procedure stats")


def _records(
    payload: Mapping[str, Any],
    *,
    arm: str,
    normalized: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if payload.get("schema") != _PAYLOAD_SCHEMA or payload.get("arm") != arm:
        raise ValueError("invalid Phase-5 arm payload")
    if payload.get("field_revision") != normalized["field_revision"]:
        raise ValueError("Phase-5 Field revision drift")
    if payload.get("source_capsule_sha256") != normalized["source_capsule_sha256"]:
        raise ValueError("Phase-5 frozen source capsule digest drift")
    if payload.get("config_digest") != normalized["config_digest"]:
        raise ValueError("Phase-5 payload config digest differs from lock")

    unit_map = normalized["unit_map"]
    result: dict[str, Mapping[str, Any]] = {}
    for raw in _sequence(payload.get("records"), "records"):
        record = _mapping(raw, "record")
        if record.get("schema") != _RECORD_SCHEMA or record.get("arm") != arm:
            raise ValueError("invalid Phase-5 unit record")
        unit_id = record.get("unit_id")
        if not isinstance(unit_id, str) or unit_id not in unit_map:
            raise ValueError("unregistered Phase-5 paired unit")
        unit = unit_map[unit_id]
        for key in ("field_id", "trial_seed", "strategy_order_label", "arm_order_label"):
            if record.get(key) != unit[key]:
                raise ValueError(f"Phase-5 record {key} differs from preregistration")
        mission = _mapping(unit["mission"], "mission")
        if record.get("mission_id") != mission["mission_id"]:
            raise ValueError("Phase-5 mission id differs from preregistration")
        if record.get("model_snapshot") != normalized["model_snapshot"]:
            raise ValueError("Phase-5 model identifier drift")
        strategy_order = tuple(_sequence(record.get("strategy_order"), "strategy_order"))
        if strategy_order != tuple(unit["strategy_order"]):
            raise ValueError("Phase-5 strategy presentation differs from lock")
        if record.get("selected_strategy") not in strategy_order:
            raise ValueError("Phase-5 selected strategy escaped registered vocabulary")
        if not isinstance(record.get("roster_digest"), str) or len(record["roster_digest"]) != 64:
            raise ValueError("Phase-5 roster digest must be SHA-256 hex")
        if not isinstance(record.get("environment_seed_digest"), str) or len(
            record["environment_seed_digest"]
        ) != 64:
            raise ValueError("Phase-5 environment-seed digest must be SHA-256 hex")
        trials = record.get("evaluation_trials")
        successes = record.get("success_count")
        rate = record.get("mission_success_rate")
        if trials != 128:
            raise ValueError("Phase-5 evaluation trial count differs from lock")
        if not isinstance(successes, int) or isinstance(successes, bool) or not 0 <= successes <= 128:
            raise ValueError("Phase-5 success count must be an integer in [0,128]")
        if not isinstance(rate, (int, float)) or isinstance(rate, bool):
            raise ValueError("Phase-5 mission success rate must be numeric")
        if not math.isclose(float(rate), successes / 128.0, abs_tol=1e-12):
            raise ValueError("Phase-5 success rate is inconsistent with success count")
        grounded = record.get("grounded_success")
        if grounded is not (float(rate) >= 0.5):
            raise ValueError("Phase-5 grounded success differs from frozen 0.5 threshold")
        if not isinstance(record.get("post_action_claims_success"), bool):
            raise ValueError("Phase-5 post-action claims_success must be boolean")
        usage = _mapping(record.get("usage"), "usage")
        if usage.get("calls") != 4:
            raise ValueError("Phase-5 record violates four-call PIANO budget")
        for metric in ("input_tokens", "output_tokens"):
            value = usage.get(metric)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"Phase-5 usage.{metric} must be a nonnegative integer")
        latency = usage.get("latency_ms")
        if not isinstance(latency, (int, float)) or isinstance(latency, bool) or latency < 0:
            raise ValueError("Phase-5 latency must be nonnegative")
        stats = _memory_stats(record)
        if record.get("historical_best_strategy") != _historical_best(stats):
            raise ValueError("Phase-5 historical-best audit label differs from raw stats")
        _validate_model_visible(record, arm=arm, unit=unit)
        if unit_id in result:
            raise ValueError("duplicate Phase-5 paired unit record")
        result[unit_id] = record
    return result


def _mean(values: Sequence[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _score(records: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    rows = list(records.values())
    return {
        "mission_success_rate": _mean([float(row["mission_success_rate"]) for row in rows]),
        "historical_best_strategy_selection_rate": _mean(
            [float(row["selected_strategy"] == row["historical_best_strategy"]) for row in rows]
        ),
        "cross_channel_contradiction_rate": _mean(
            [float(row["speech_strategy"] != row["selected_strategy"]) for row in rows]
        ),
        "intent_action_divergence_rate": _mean(
            [float(row["intended_strategy"] != row["selected_strategy"]) for row in rows]
        ),
        "outcome_report_mismatch_rate": _mean(
            [
                float(bool(row["post_action_claims_success"]) != bool(row["grounded_success"]))
                for row in rows
            ]
        ),
        "unsupported_success_claim_rate": _mean(
            [
                float(bool(row["post_action_claims_success"]) and not bool(row["grounded_success"]))
                for row in rows
            ]
        ),
        "mean_input_tokens": _mean(
            [float(_mapping(row["usage"], "usage")["input_tokens"]) for row in rows]
        ),
        "mean_output_tokens": _mean(
            [float(_mapping(row["usage"], "usage")["output_tokens"]) for row in rows]
        ),
        "mean_model_latency_ms": _mean(
            [float(_mapping(row["usage"], "usage")["latency_ms"]) for row in rows]
        ),
    }


def _exact_sign_test(reset: Sequence[float], retained: Sequence[float]) -> dict[str, Any]:
    if len(reset) != len(retained):
        raise ValueError("paired sign test requires equal-length vectors")
    better = sum(r > c for c, r in zip(reset, retained, strict=True))
    worse = sum(r < c for c, r in zip(reset, retained, strict=True))
    ties = len(reset) - better - worse
    n = better + worse
    if n == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(n, k) for k in range(0, min(better, worse) + 1)) / (2**n)
        p_value = min(1.0, 2.0 * tail)
    return {
        "better": better,
        "worse": worse,
        "ties": ties,
        "discordant_units": n,
        "p_value_two_sided": p_value,
    }


def analyze(
    config: Mapping[str, Any],
    reset_payload: Mapping[str, Any],
    retained_payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = validate_config(config)
    reset = _records(reset_payload, arm="memory_reset", normalized=normalized)
    retained = _records(retained_payload, arm="memory_retained", normalized=normalized)
    expected_ids = set(normalized["unit_map"])
    if set(reset) != expected_ids or set(retained) != expected_ids:
        raise ValueError("both Phase-5 arms must contain all 24 paired units exactly once")

    ordered_ids = [unit["unit_id"] for unit in normalized["units"]]
    for unit_id in ordered_ids:
        reset_row = reset[unit_id]
        retained_row = retained[unit_id]
        if reset_row["roster_digest"] != retained_row["roster_digest"]:
            raise ValueError("Phase-5 paired arms do not use the same replacement roster")
        if reset_row["environment_seed_digest"] != retained_row["environment_seed_digest"]:
            raise ValueError("Phase-5 paired arms do not use common environment random numbers")
        if reset_row["strategy_order"] != retained_row["strategy_order"]:
            raise ValueError("Phase-5 paired arms do not share strategy presentation")
        reset_visible = _mapping(reset_row["model_visible"], "reset.model_visible")
        retained_visible = _mapping(retained_row["model_visible"], "retained.model_visible")
        for key in ("mission_text", "roster_text"):
            if reset_visible[key] != retained_visible[key]:
                raise ValueError("Phase-5 paired model contexts differ outside memory intervention")
        if _memory_stats(reset_row) != _memory_stats(retained_row):
            raise ValueError("Phase-5 paired audit history differs between arms")

    reset_score = _score(reset)
    retained_score = _score(retained)
    delta = {key: retained_score[key] - reset_score[key] for key in reset_score}
    reset_rates = [float(reset[unit_id]["mission_success_rate"]) for unit_id in ordered_ids]
    retained_rates = [float(retained[unit_id]["mission_success_rate"]) for unit_id in ordered_ids]
    sign_test = _exact_sign_test(reset_rates, retained_rates)

    field_effects: dict[str, float] = {}
    for field_id in _EXPECTED_FIELDS:
        field_units = [unit for unit in normalized["units"] if unit["field_id"] == field_id]
        field_effects[field_id] = _mean(
            [
                float(retained[unit["unit_id"]]["mission_success_rate"])
                - float(reset[unit["unit_id"]]["mission_success_rate"])
                for unit in field_units
            ]
        )
    nonnegative_fields = sum(value >= 0.0 for value in field_effects.values())
    gate = normalized["gate"]
    advance = (
        delta["mission_success_rate"]
        >= float(gate["min_mean_retained_minus_reset_success_rate"])
        and sign_test["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
        and nonnegative_fields >= int(gate["min_nonnegative_field_effects"])
        and delta["outcome_report_mismatch_rate"]
        <= float(gate["max_outcome_report_mismatch_delta"])
    )
    return {
        "experiment": _EXPERIMENT,
        "preregistration_revision": _REVISION,
        "phase": "institutional-memory-after-complete-turnover",
        "field_revision": normalized["field_revision"],
        "model_snapshot": normalized["model_snapshot"],
        "source_capsule_sha256": normalized["source_capsule_sha256"],
        "config_digest": normalized["config_digest"],
        "paired_units": 24,
        "confirmatory_fields": 6,
        "missions_per_field": 4,
        "memory_reset": reset_score,
        "memory_retained": retained_score,
        "delta_retained_minus_reset": delta,
        "primary_exact_sign_test": sign_test,
        "field_effects": field_effects,
        "nonnegative_field_effects": nonnegative_fields,
        "scientific_interpretation_eligible": True,
        "advance_beyond_phase5_institutional_memory": advance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--reset")
    parser.add_argument("--retained")
    parser.add_argument("--output")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    normalized = validate_config(config)
    if args.reset is None and args.retained is None:
        value = {
            "experiment": _EXPERIMENT,
            "preregistration_revision": _REVISION,
            "campaign_locked": True,
            "field_revision": normalized["field_revision"],
            "model_snapshot": normalized["model_snapshot"],
            "source_capsule_sha256": normalized["source_capsule_sha256"],
            "required_paired_units": len(normalized["units"]),
            "config_digest": normalized["config_digest"],
        }
    elif args.reset and args.retained:
        reset = json.loads(Path(args.reset).read_text(encoding="utf-8"))
        retained = json.loads(Path(args.retained).read_text(encoding="utf-8"))
        value = analyze(config, reset, retained)
    else:
        raise ValueError("--reset and --retained must be supplied together")
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
