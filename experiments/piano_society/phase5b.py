"""Preregistered analysis for PIANO Phase-5B transferable institutional memory."""

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

_EXPERIMENT = "piano-society-runtime-v0-phase5b-transferable-memory"
_REVISION = "glm5.2-transferable-institutional-model-v1"
_FIELD_SHA = "e877bf03dbf6681ce7cbd98d984e73c032e911aa"
_MODEL = "glm-5.2"
_ARMS = ("model_reset", "model_retained")
_STRATEGIES = ("specialist", "balanced")
_PAYLOAD_SCHEMA = "resonance-world-piano-phase5b-arm-v0.1"
_RECORD_SCHEMA = "resonance-world-piano-phase5b-unit-v0.1"
_SOURCE_CAPSULE_SHA = "3db71e9b498605853454abe64c0937f032e8d91bf0500c76fe20b17c9e436ebd"
_REAL_SKILLS = (
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
)
_EXPECTED_FIELDS = (
    "w4-source-seed-13217",
    "w4-source-seed-13331",
    "w4-source-seed-13441",
    "w4-source-seed-13553",
    "w4-source-seed-13669",
    "w4-source-seed-13781",
)
_EXPECTED_MISSIONS = (
    ("route-a", "supply_networks", "urban_heat", "balanced", "skill-d", "skill-a"),
    ("route-b", "urban_heat", "supply_networks", "balanced", "skill-a", "skill-d"),
    ("route-c", "energy_storage", "urban_heat", "specialist", "skill-c", "skill-a"),
    ("route-d", "public_health", "urban_heat", "specialist", "skill-e", "skill-a"),
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


def _exact_sign_test(better: int, worse: int) -> float:
    discordant = better + worse
    if discordant == 0:
        return 1.0
    tail = min(better, worse)
    one_tail = sum(math.comb(discordant, k) for k in range(tail + 1)) / (2**discordant)
    return min(1.0, 2.0 * one_tail)


def _preferred_strategy(forecasts: Mapping[str, Any]) -> tuple[str, float]:
    if set(forecasts) != set(_STRATEGIES):
        raise ValueError("strategy forecast must contain specialist and balanced exactly")
    values: dict[str, float] = {}
    for strategy in _STRATEGIES:
        value = forecasts[strategy]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("strategy forecasts must be numeric")
        values[strategy] = float(value)
        if not 0.0 <= values[strategy] <= 1.0:
            raise ValueError("strategy forecast must lie in [0, 1]")
    preferred = max(
        _STRATEGIES,
        key=lambda strategy: (values[strategy], -_STRATEGIES.index(strategy)),
    )
    return preferred, abs(values["specialist"] - values["balanced"])


def materialize_units(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = _mapping(config.get("source_lock"), "source_lock")
    fields = tuple(str(item) for item in _sequence(source.get("confirmatory_fields"), "fields"))
    if fields != _EXPECTED_FIELDS:
        raise ValueError("Phase-5B confirmatory field set/order differs from lock")
    raw_missions = _sequence(config.get("missions"), "missions")
    if len(raw_missions) != 4:
        raise ValueError("Phase-5B requires exactly four missions")
    missions: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_missions):
        row = _mapping(raw, "mission")
        expected = _EXPECTED_MISSIONS[index]
        observed = (
            row.get("mission_id"),
            row.get("lead_skill"),
            row.get("support_skill"),
            row.get("hidden_regime"),
            row.get("public_lead_skill"),
            row.get("public_support_skill"),
        )
        if observed != expected or row.get("context") != expected[0]:
            raise ValueError("Phase-5B mission set differs from v2 search lock")
        missions.append(dict(row))

    units: list[dict[str, Any]] = []
    strategy_counts: Counter[str] = Counter()
    arm_counts: Counter[str] = Counter()
    cross_counts: Counter[tuple[str, str]] = Counter()
    for field_index, field_id in enumerate(fields):
        for mission_index, mission in enumerate(missions):
            specialist_first = (field_index + mission_index) % 2 == 0
            strategy_order = (
                ("specialist", "balanced") if specialist_first else ("balanced", "specialist")
            )
            strategy_label = "specialist_first" if specialist_first else "balanced_first"
            retained_first = field_index % 2 == 0
            arm_order = (
                ("model_retained", "model_reset")
                if retained_first
                else ("model_reset", "model_retained")
            )
            arm_label = "model_retained_first" if retained_first else "model_reset_first"
            unit_id = f"{field_id}::{mission['mission_id']}"
            units.append(
                {
                    "unit_id": unit_id,
                    "field_id": field_id,
                    "field_index": field_index,
                    "mission_index": mission_index,
                    "mission": mission,
                    "trial_seed": 970000 + field_index * 100 + mission_index,
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
        raise ValueError("Phase-5B requires exactly 24 paired units")
    if strategy_counts != Counter({"specialist_first": 12, "balanced_first": 12}):
        raise ValueError("Phase-5B strategy presentation is not 12/12")
    if arm_counts != Counter({"model_retained_first": 12, "model_reset_first": 12}):
        raise ValueError("Phase-5B arm order is not 12/12")
    if len(cross_counts) != 4 or any(value != 6 for value in cross_counts.values()):
        raise ValueError("Phase-5B strategy/arm presentation must cross-balance six each")
    return units


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _EXPERIMENT:
        raise ValueError("unsupported Phase-5B experiment identifier")
    if config.get("preregistration_revision") != _REVISION:
        raise ValueError("unexpected Phase-5B preregistration revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-5B campaign must be locked")
    if config.get("field_revision") != _FIELD_SHA or config.get("required_model_snapshot") != _MODEL:
        raise ValueError("Phase-5B Field/model binding differs from lock")

    prerequisite = _mapping(config.get("validated_prerequisites"), "validated_prerequisites")
    expected_prerequisite = {
        "phase4c_world_revision": "b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1",
        "phase4c_workflow_run": 31638087507,
        "phase4c_artifact_id": 9158432521,
        "phase4c_artifact_digest": "sha256:465c5d07c7e98a33dccedf24c0fb504a82ad54632590ec1fce8eddd1cf57279e",
        "phase4c_advance_to_phase5": True,
        "phase5_world_revision": "7671f683c3dcc9c93a6de2a1f0245e8b6f443d88",
        "phase5_workflow_run": 31642962282,
        "phase5_artifact_id": 9159703582,
        "phase5_artifact_digest": "sha256:b22f618199188272c048f0cb2d1b985abd5f750fab0623f34edbc76b07c096e0",
        "phase5_result_commit": "faec7ddc1ee01013f7a6ebfd427c5ae8726a06bf",
        "phase5_mean_retained_minus_reset_success_rate": 0.006184895833333315,
        "phase5_primary_sign_test_p": 0.7265625,
        "phase5_advance": False,
    }
    if dict(prerequisite) != expected_prerequisite:
        raise ValueError("Phase-5B prerequisite binding differs from lock")

    source = _mapping(config.get("source_lock"), "source_lock")
    expected_source = {
        "workflow_run": 31649544130,
        "world_revision": "55668e2f5aa74baa070d2c7fcfc2a2e77de26e8f",
        "artifact_id": 9162069554,
        "artifact_name": "piano-society-phase5b-frozen-source",
        "artifact_digest": "sha256:f91b0d23cf3a5b78c100ecacba0fc873bcfc3f5db18ee9a7ed17900d14c793b5",
        "capsule_sha256": _SOURCE_CAPSULE_SHA,
        "candidate_sha256": "ca6a9317358643fdf22464512447b800b4336470b3488b03764a9dd3cc862190",
        "field_count": 8,
        "agent_count": 96,
        "calibration_fields": ["w4-source-seed-13007", "w4-source-seed-13109"],
        "confirmatory_fields": list(_EXPECTED_FIELDS),
    }
    if dict(source) != expected_source:
        raise ValueError("Phase-5B exact frozen-source binding differs from lock")

    search = _mapping(config.get("transfer_search_lock"), "transfer_search_lock")
    expected_search = {
        "workflow_run": 31649908290,
        "world_revision": "dbaae3d0bf672befa43583510b8f7bcd6ca2fcf7",
        "artifact_id": 9162175324,
        "artifact_name": "piano-society-phase5b-v2-transfer-search",
        "artifact_digest": "sha256:f82f936d6d37a1d88967cabd7d698936bdc6234af2674585c4d2377c22f24d4c",
        "revision": "piano-phase5b-transfer-search-v2",
        "model_calls": 0,
        "formation_depth": 96,
        "candidate_count": 60,
        "selected_unit_count": 8,
        "mean_selected_transfer_policy_lift_over_neutral_policy": 0.03662109375,
        "nonnegative_selected_units": 8,
        "posterior_structure_matches": 8,
        "accepted": True,
    }
    if dict(search) != expected_search:
        raise ValueError("Phase-5B v2 search binding differs from lock")

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
        "strategy_order": "specialist_first_when_field_index_plus_mission_index_even_else_balanced_first",
    }
    if dict(backend) != expected_backend:
        raise ValueError("Phase-5B provider transport differs from lock")

    memory = _mapping(config.get("institutional_model_memory"), "institutional_model_memory")
    expected_memory = {
        "formation_depth": 96,
        "formation_strategy_order": ["specialist", "balanced"],
        "turnover_fraction": 1.0,
        "structural_hypotheses": ["role_specific", "cross_coverage"],
        "reset_prior": {"role_specific": 0.5, "cross_coverage": 0.5},
        "retained_posterior_source": "organization_owned_pre_turnover_episodes",
        "forecast_uses_current_replacement_roster": True,
        "model_visible_memory": "structural_posterior_plus_current_roster_strategy_forecast",
        "model_visible_hidden_regime": False,
        "environment_reads_memory": False,
        "evaluation_updates_memory": False,
        "strategy_vocabulary": ["specialist", "balanced"],
        "evaluation_trials_per_unit": 128,
        "grounded_success_threshold": 0.5,
        "decisive_forecast_epsilon": 1e-12,
    }
    if dict(memory) != expected_memory:
        raise ValueError("Phase-5B memory intervention differs from lock")

    aliases = _mapping(config.get("skill_aliases"), "skill_aliases")
    if dict(aliases) != {
        "urban_heat": "skill-a",
        "water_systems": "skill-b",
        "energy_storage": "skill-c",
        "supply_networks": "skill-d",
        "public_health": "skill-e",
        "mobility": "skill-f",
    }:
        raise ValueError("Phase-5B skill aliases differ from lock")
    if tuple(config.get("arms", ())) != _ARMS:
        raise ValueError("Phase-5B arms differ from lock")
    if config.get("confirmatory_field_count") != 6 or config.get("missions_per_field") != 4:
        raise ValueError("Phase-5B dimensions differ from lock")
    if config.get("required_paired_units") != 24:
        raise ValueError("Phase-5B requires 24 paired units")
    if config.get("calls_per_arm_unit") != 4 or config.get("max_output_tokens_per_call") != 128:
        raise ValueError("Phase-5B model budget differs from lock")
    if config.get("strategy_order_counts") != {"specialist_first": 12, "balanced_first": 12}:
        raise ValueError("Phase-5B strategy-order count lock differs")
    if config.get("arm_order_counts") != {
        "model_retained_first": 12,
        "model_reset_first": 12,
    }:
        raise ValueError("Phase-5B arm-order count lock differs")
    if config.get("presentation_arm_cross_count_each") != 6:
        raise ValueError("Phase-5B presentation/arm cross lock differs")
    if config.get("primary_metric") != "mission_success_rate":
        raise ValueError("Phase-5B primary metric differs from lock")

    gate = _mapping(config.get("advancement_gate"), "advancement_gate")
    expected_gate = {
        "min_mean_retained_minus_reset_success_rate": 0.03,
        "max_primary_sign_test_p": 0.05,
        "min_nonnegative_field_effects": 4,
        "max_outcome_report_mismatch_delta": 0.05,
        "min_decisive_forecast_units_each_arm": 8,
        "min_forecast_fidelity_each_arm": 0.9,
    }
    if dict(gate) != expected_gate:
        raise ValueError("Phase-5B advancement gate differs from lock")

    units = materialize_units(config)
    return {
        "field_revision": _FIELD_SHA,
        "model_snapshot": _MODEL,
        "source_capsule_sha256": _SOURCE_CAPSULE_SHA,
        "units": units,
        "unit_map": {unit["unit_id"]: unit for unit in units},
        "gate": gate,
        "epsilon": 1e-12,
        "config_digest": config_digest(config),
    }


def _validate_memory(record: Mapping[str, Any], arm: str, epsilon: float) -> tuple[str, bool]:
    visible = _mapping(record.get("model_visible"), "model_visible")
    serialized = json.dumps(visible, sort_keys=True)
    for skill in _REAL_SKILLS:
        if skill in serialized:
            raise ValueError("real skill name leaked into Phase-5B model-visible payload")
    if "hidden_regime" in serialized:
        raise ValueError("hidden regime key leaked into Phase-5B model-visible payload")
    memory = _mapping(visible.get("institutional_model_memory"), "institutional_model_memory")
    posterior = _mapping(memory.get("structural_posterior"), "structural_posterior")
    if set(posterior) != {"role_specific", "cross_coverage", "evidence_episodes"}:
        raise ValueError("structural posterior schema differs from lock")
    role = posterior["role_specific"]
    cross = posterior["cross_coverage"]
    evidence = posterior["evidence_episodes"]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (role, cross)):
        raise ValueError("structural posterior probabilities must be numeric")
    if not isinstance(evidence, int) or isinstance(evidence, bool) or evidence < 0:
        raise ValueError("evidence_episodes must be a non-negative integer")
    if not math.isclose(float(role) + float(cross), 1.0, abs_tol=1e-9):
        raise ValueError("structural posterior must sum to one")
    if arm == "model_reset":
        if evidence != 0 or not math.isclose(float(role), 0.5, abs_tol=1e-12) or not math.isclose(float(cross), 0.5, abs_tol=1e-12):
            raise ValueError("reset arm must expose the exact neutral prior")
    else:
        if evidence != 192:
            raise ValueError("retained arm must expose exactly 192 formation episodes")
    forecasts = _mapping(memory.get("current_roster_strategy_forecast"), "forecasts")
    preferred, margin = _preferred_strategy(forecasts)
    decisive = margin > epsilon
    audit = _mapping(record.get("audit"), "audit")
    if audit.get("forecast_preferred_strategy") != preferred:
        raise ValueError("runner forecast-preferred strategy differs from analyzer recomputation")
    if not math.isclose(float(audit.get("forecast_margin", -1.0)), margin, abs_tol=1e-12):
        raise ValueError("runner forecast margin differs from analyzer recomputation")
    if audit.get("decisive_forecast") is not decisive:
        raise ValueError("runner decisive-forecast flag differs from analyzer recomputation")
    return preferred, decisive


def _validate_record(
    record: Mapping[str, Any],
    *,
    arm: str,
    unit: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    if record.get("schema") != _RECORD_SCHEMA:
        raise ValueError("Phase-5B record schema differs from lock")
    if record.get("arm") != arm or record.get("unit_id") != unit["unit_id"]:
        raise ValueError("Phase-5B arm/unit identity differs from lock")
    if record.get("field_id") != unit["field_id"] or record.get("mission_id") != unit["mission"]["mission_id"]:
        raise ValueError("Phase-5B field/mission identity differs from lock")
    if record.get("trial_seed") != unit["trial_seed"]:
        raise ValueError("Phase-5B trial seed differs from lock")
    if record.get("field_revision") != _FIELD_SHA or record.get("model_snapshot") != _MODEL:
        raise ValueError("Phase-5B record Field/model drift")
    if record.get("config_digest") != lock["config_digest"]:
        raise ValueError("Phase-5B record config digest differs from lock")
    if tuple(record.get("strategy_order", ())) != tuple(unit["strategy_order"]):
        raise ValueError("Phase-5B strategy presentation differs from lock")
    if record.get("arm_order_label") != unit["arm_order_label"]:
        raise ValueError("Phase-5B arm-order label differs from lock")

    audit = _mapping(record.get("audit"), "audit")
    if audit.get("hidden_regime") != unit["mission"]["hidden_regime"]:
        raise ValueError("Phase-5B audit regime differs from registered mission")
    chosen = audit.get("chosen_strategy")
    intended = audit.get("intended_strategy")
    speech = audit.get("speech_strategy")
    if chosen not in _STRATEGIES or intended not in _STRATEGIES or speech not in _STRATEGIES:
        raise ValueError("Phase-5B strategy label outside binary vocabulary")
    preferred, decisive = _validate_memory(record, arm, float(lock["epsilon"]))

    trials = audit.get("evaluation_trials")
    successes = audit.get("success_count")
    rate = audit.get("mission_success_rate")
    if trials != 128 or not isinstance(successes, int) or isinstance(successes, bool):
        raise ValueError("Phase-5B evaluation count differs from lock")
    if not 0 <= successes <= 128:
        raise ValueError("Phase-5B success count outside [0, 128]")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise ValueError("Phase-5B success rate must be numeric")
    if not math.isclose(float(rate), successes / 128.0, abs_tol=1e-12):
        raise ValueError("Phase-5B success rate inconsistent with count")
    grounded = float(rate) >= 0.5
    if audit.get("grounded_success") is not grounded:
        raise ValueError("Phase-5B grounded-success flag differs from registered threshold")
    claims = audit.get("post_action_claims_success")
    if not isinstance(claims, bool):
        raise ValueError("Phase-5B post-action claims_success must be boolean")

    usage = _mapping(record.get("usage"), "usage")
    if usage.get("calls") != 4:
        raise ValueError("Phase-5B record must contain exactly four logical model calls")
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("Phase-5B token counts must be non-negative integers")
    latency = usage.get("latency_ms")
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or float(latency) < 0:
        raise ValueError("Phase-5B latency must be non-negative")

    roster_digest = record.get("replacement_roster_digest")
    seed_digest = record.get("environment_trial_seed_digest")
    if not isinstance(roster_digest, str) or len(roster_digest) != 64:
        raise ValueError("Phase-5B replacement roster digest malformed")
    if not isinstance(seed_digest, str) or len(seed_digest) != 64:
        raise ValueError("Phase-5B environment seed digest malformed")

    return {
        "success_rate": float(rate),
        "chosen": str(chosen),
        "preferred": preferred,
        "decisive": decisive,
        "forecast_fidelity": bool(chosen == preferred),
        "contradiction": bool(speech != chosen),
        "intent_divergence": bool(intended != chosen),
        "report_mismatch": bool(claims != grounded),
        "unsupported_success": bool(claims and not grounded),
        "input_tokens": int(usage["input_tokens"]),
        "output_tokens": int(usage["output_tokens"]),
        "latency_ms": float(latency),
        "roster_digest": roster_digest,
        "seed_digest": seed_digest,
        "model_visible": dict(_mapping(record.get("model_visible"), "model_visible")),
    }


def _arm_records(payload: Mapping[str, Any], arm: str, lock: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if payload.get("schema") != _PAYLOAD_SCHEMA or payload.get("arm") != arm:
        raise ValueError("Phase-5B arm payload schema/arm differs from lock")
    if payload.get("field_revision") != _FIELD_SHA or payload.get("model_snapshot") != _MODEL:
        raise ValueError("Phase-5B arm payload Field/model drift")
    if payload.get("source_capsule_sha256") != _SOURCE_CAPSULE_SHA:
        raise ValueError("Phase-5B source capsule differs from frozen source")
    if payload.get("config_digest") != lock["config_digest"]:
        raise ValueError("Phase-5B arm payload config digest differs from lock")
    records = _sequence(payload.get("records"), "records")
    if len(records) != 24:
        raise ValueError("Phase-5B arm payload must contain 24 records")
    result: dict[str, Mapping[str, Any]] = {}
    for raw in records:
        record = _mapping(raw, "record")
        unit_id = record.get("unit_id")
        if not isinstance(unit_id, str) or unit_id in result:
            raise ValueError("Phase-5B unit IDs must be unique strings")
        result[unit_id] = record
    if set(result) != set(lock["unit_map"]):
        raise ValueError("Phase-5B arm payload unit set differs from lock")
    return result


def analyze(config: Mapping[str, Any], reset_payload: Mapping[str, Any], retained_payload: Mapping[str, Any]) -> dict[str, Any]:
    lock = validate_config(config)
    raw_by_arm = {
        "model_reset": _arm_records(reset_payload, "model_reset", lock),
        "model_retained": _arm_records(retained_payload, "model_retained", lock),
    }
    metrics: dict[str, dict[str, Any]] = {arm: {} for arm in _ARMS}
    validated: dict[str, dict[str, dict[str, Any]]] = {arm: {} for arm in _ARMS}
    for unit in lock["units"]:
        unit_id = unit["unit_id"]
        for arm in _ARMS:
            validated[arm][unit_id] = _validate_record(
                raw_by_arm[arm][unit_id], arm=arm, unit=unit, lock=lock
            )
        reset = validated["model_reset"][unit_id]
        retained = validated["model_retained"][unit_id]
        if reset["roster_digest"] != retained["roster_digest"]:
            raise ValueError("Phase-5B paired arms must share the exact replacement roster")
        if reset["seed_digest"] != retained["seed_digest"]:
            raise ValueError("Phase-5B paired arms must share the exact environment trial seeds")
        reset_visible = dict(reset["model_visible"])
        retained_visible = dict(retained["model_visible"])
        reset_memory = reset_visible.pop("institutional_model_memory")
        retained_memory = retained_visible.pop("institutional_model_memory")
        if reset_visible != retained_visible:
            raise ValueError("Phase-5B paired model-visible context differs outside memory intervention")
        if reset_memory == retained_memory:
            raise ValueError("Phase-5B paired memory intervention is unexpectedly identical")

    for arm in _ARMS:
        rows = list(validated[arm].values())
        decisive = [row for row in rows if row["decisive"]]
        metrics[arm] = {
            "mission_success_rate": statistics.mean(row["success_rate"] for row in rows),
            "decisive_forecast_units": len(decisive),
            "forecast_fidelity_rate": (
                statistics.mean(float(row["forecast_fidelity"]) for row in decisive)
                if decisive
                else 0.0
            ),
            "cross_channel_contradiction_rate": statistics.mean(float(row["contradiction"]) for row in rows),
            "intent_action_divergence_rate": statistics.mean(float(row["intent_divergence"]) for row in rows),
            "outcome_report_mismatch_rate": statistics.mean(float(row["report_mismatch"]) for row in rows),
            "unsupported_success_claim_rate": statistics.mean(float(row["unsupported_success"]) for row in rows),
            "mean_input_tokens": statistics.mean(row["input_tokens"] for row in rows),
            "mean_output_tokens": statistics.mean(row["output_tokens"] for row in rows),
            "mean_model_latency_ms": statistics.mean(row["latency_ms"] for row in rows),
        }

    paired_effects: list[float] = []
    better = worse = ties = 0
    changed_actions = 0
    field_effects: dict[str, list[float]] = {field_id: [] for field_id in _EXPECTED_FIELDS}
    for unit in lock["units"]:
        unit_id = unit["unit_id"]
        reset = validated["model_reset"][unit_id]
        retained = validated["model_retained"][unit_id]
        effect = retained["success_rate"] - reset["success_rate"]
        paired_effects.append(effect)
        field_effects[unit["field_id"]].append(effect)
        if effect > 0:
            better += 1
        elif effect < 0:
            worse += 1
        else:
            ties += 1
        if retained["chosen"] != reset["chosen"]:
            changed_actions += 1
    field_mean_effects = {
        field_id: statistics.mean(values) for field_id, values in field_effects.items()
    }
    nonnegative_fields = sum(value >= 0.0 for value in field_mean_effects.values())
    sign_p = _exact_sign_test(better, worse)
    mean_effect = statistics.mean(paired_effects)
    report_mismatch_delta = (
        metrics["model_retained"]["outcome_report_mismatch_rate"]
        - metrics["model_reset"]["outcome_report_mismatch_rate"]
    )
    gate = lock["gate"]
    advance = (
        mean_effect >= float(gate["min_mean_retained_minus_reset_success_rate"])
        and sign_p <= float(gate["max_primary_sign_test_p"])
        and nonnegative_fields >= int(gate["min_nonnegative_field_effects"])
        and report_mismatch_delta <= float(gate["max_outcome_report_mismatch_delta"])
        and all(
            metrics[arm]["decisive_forecast_units"]
            >= int(gate["min_decisive_forecast_units_each_arm"])
            for arm in _ARMS
        )
        and all(
            metrics[arm]["forecast_fidelity_rate"]
            >= float(gate["min_forecast_fidelity_each_arm"])
            for arm in _ARMS
        )
    )
    return {
        "experiment": _EXPERIMENT,
        "preregistration_revision": _REVISION,
        "scientific_interpretation_eligible": True,
        "records_per_arm": 24,
        "paired_units": 24,
        "metrics": metrics,
        "primary": {
            "mean_retained_minus_reset_success_rate": mean_effect,
            "paired_better": better,
            "paired_worse": worse,
            "paired_ties": ties,
            "paired_discordant": better + worse,
            "exact_two_sided_sign_test_p": sign_p,
            "field_mean_effects": field_mean_effects,
            "nonnegative_field_effects": nonnegative_fields,
        },
        "mechanism": {
            "forecast_action_change_units": changed_actions,
            "forecast_action_change_rate": changed_actions / 24.0,
            "outcome_report_mismatch_delta": report_mismatch_delta,
        },
        "advancement_gate": dict(gate),
        "advance_beyond_phase5b_transferable_memory": advance,
        "config_digest": lock["config_digest"],
        "dataset_digest": _canonical_digest(
            {
                "model_reset": reset_payload,
                "model_retained": retained_payload,
            }
        ),
    }


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("reset")
    parser.add_argument("retained")
    parser.add_argument("output")
    args = parser.parse_args()
    result = analyze(_load(args.config), _load(args.reset), _load(args.retained))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
