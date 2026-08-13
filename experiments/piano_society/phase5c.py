"""Preregistered analyzer for PIANO Phase-5C decision-relevant memory."""

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

_EXPERIMENT = "piano-society-runtime-v0-phase5c-decision-relevant-memory"
_REVISION = "glm5.2-decision-relevant-institutional-memory-v1"
_FIELD_SHA = "e877bf03dbf6681ce7cbd98d984e73c032e911aa"
_MODEL = "glm-5.2"
_ARMS = ("model_reset", "model_retained")
_STRATEGIES = ("specialist", "balanced")
_PAYLOAD_SCHEMA = "resonance-world-piano-phase5c-arm-v0.1"
_RECORD_SCHEMA = "resonance-world-piano-phase5c-unit-v0.1"
_SOURCE_CAPSULE_SHA = "b44926d70fe91ae3ad546351bd42096ad54a10d7d50eb954060e1bc56dcd1ea8"
_UNITS_SHA = "b566f286bff62843833fcb43afbc4c9ef325caa57ed42bdb557a622c77e4d720"
_BACKEND_SHA = "ff2cffe9c9243c2599e5851a2febe109949e08cae1ec919a358860a2587da2cb"
_MEMORY_SHA = "76ccd9b7ba0d8a380930ac1498c84e4ea1c9fc344307b92e3f26183571b6708b"
_GATE_SHA = "d9baf0d68c1e5189b978794ee2c5301ba9f7f913bbc8badd78aa26db0a968e42"
_REAL_SKILLS = (
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
)
_PRIVATE_KEYS = (
    '"target_hypothesis"',
    '"hidden_regime"',
    '"target_policy"',
    '"neutral_preferred_policy"',
)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    return value


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _exact_sign_test(better: int, worse: int) -> float:
    discordant = better + worse
    if discordant == 0:
        return 1.0
    tail = min(better, worse)
    one_tail = sum(math.comb(discordant, k) for k in range(tail + 1)) / (2**discordant)
    return min(1.0, 2.0 * one_tail)


def _preferred(forecasts: Mapping[str, Any]) -> tuple[str, float]:
    if set(forecasts) != set(_STRATEGIES):
        raise ValueError("Phase-5C forecasts must contain specialist/balanced exactly")
    values: dict[str, float] = {}
    for strategy in _STRATEGIES:
        value = forecasts[strategy]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Phase-5C forecasts must be numeric")
        values[strategy] = float(value)
        if not 0.0 <= values[strategy] <= 1.0:
            raise ValueError("Phase-5C forecast outside [0, 1]")
    preferred = max(
        _STRATEGIES,
        key=lambda strategy: (values[strategy], -_STRATEGIES.index(strategy)),
    )
    return preferred, abs(values["specialist"] - values["balanced"])


def materialize_units(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_units = [dict(_mapping(item, "unit")) for item in _sequence(config.get("units"), "units")]
    if len(raw_units) != 12 or _digest(raw_units) != _UNITS_SHA:
        raise ValueError("Phase-5C confirmatory unit lock differs")
    units: list[dict[str, Any]] = []
    strategy_counts: Counter[str] = Counter()
    arm_counts: Counter[str] = Counter()
    cross_counts: Counter[tuple[str, str]] = Counter()
    for index, row in enumerate(raw_units):
        specialist_first = index % 2 == 0
        strategy_order = (
            ("specialist", "balanced") if specialist_first else ("balanced", "specialist")
        )
        strategy_label = "specialist_first" if specialist_first else "balanced_first"
        retained_first = index % 4 < 2
        arm_order = (
            ("model_retained", "model_reset")
            if retained_first
            else ("model_reset", "model_retained")
        )
        arm_label = "model_retained_first" if retained_first else "model_reset_first"
        unit = {
            **row,
            "pair_index": index,
            "trial_seed": 990000 + index,
            "strategy_order": strategy_order,
            "strategy_order_label": strategy_label,
            "arm_order": arm_order,
            "arm_order_label": arm_label,
        }
        units.append(unit)
        strategy_counts[strategy_label] += 1
        arm_counts[arm_label] += 1
        cross_counts[(strategy_label, arm_label)] += 1
    if strategy_counts != Counter({"specialist_first": 6, "balanced_first": 6}):
        raise ValueError("Phase-5C strategy order is not 6/6")
    if arm_counts != Counter({"model_retained_first": 6, "model_reset_first": 6}):
        raise ValueError("Phase-5C arm order is not 6/6")
    if len(cross_counts) != 4 or any(value != 3 for value in cross_counts.values()):
        raise ValueError("Phase-5C arm/strategy presentation is not crossed 3 per cell")
    return units


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _EXPERIMENT or config.get("preregistration_revision") != _REVISION:
        raise ValueError("unsupported Phase-5C experiment/revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-5C campaign must be locked")
    if config.get("field_revision") != _FIELD_SHA or config.get("required_model_snapshot") != _MODEL:
        raise ValueError("Phase-5C Field/model binding differs")
    source = _mapping(config.get("source_lock"), "source_lock")
    if source.get("workflow_run") != 31652358960 or source.get("artifact_id") != 9163101495:
        raise ValueError("Phase-5C source artifact binding differs")
    if source.get("artifact_digest") != "sha256:2caf65e6f2839f243ad0c6e59f7d12ad196f48ddf79aab7c3cca42b0904f22f6":
        raise ValueError("Phase-5C source artifact digest differs")
    if source.get("capsule_sha256") != _SOURCE_CAPSULE_SHA:
        raise ValueError("Phase-5C capsule binding differs")
    geometry = _mapping(config.get("geometry_audit_lock"), "geometry_audit_lock")
    if geometry.get("workflow_run") != 31652891403 or geometry.get("artifact_id") != 9163248092:
        raise ValueError("Phase-5C geometry-audit binding differs")
    if geometry.get("selected_composition") != {"role_specific": 5, "cross_coverage": 7}:
        raise ValueError("Phase-5C target composition differs from audited feasible lock")
    constructor = _mapping(config.get("constructor_lock"), "constructor_lock")
    if constructor.get("workflow_run") != 31653068347 or constructor.get("artifact_id") != 9163310926:
        raise ValueError("Phase-5C constructor binding differs")
    if constructor.get("artifact_digest") != "sha256:e4a7c0dcf11d7d3288d1a97acd13b8814752b1629cd9fde997f093c63601a13d":
        raise ValueError("Phase-5C constructor artifact digest differs")
    if constructor.get("accepted") is not True or constructor.get("confirmatory_outcomes_evaluated") is not False:
        raise ValueError("Phase-5C constructor scientific prerequisite differs")
    if constructor.get("calibration_mean_retained_minus_neutral_success_rate") != 0.0302734375:
        raise ValueError("Phase-5C calibration effect differs")
    if any(constructor.get(key) != 4 for key in (
        "calibration_nonnegative_units",
        "calibration_forecast_preference_change_units",
        "calibration_target_posterior_match_units",
    )):
        raise ValueError("Phase-5C calibration mechanism gate differs")
    if _digest(dict(_mapping(config.get("model_backend"), "model_backend"))) != _BACKEND_SHA:
        raise ValueError("Phase-5C provider transport differs from lock")
    if _digest(dict(_mapping(config.get("institutional_model_memory"), "memory"))) != _MEMORY_SHA:
        raise ValueError("Phase-5C memory intervention differs from lock")
    if _digest(dict(_mapping(config.get("advancement_gate"), "gate"))) != _GATE_SHA:
        raise ValueError("Phase-5C advancement gate differs from lock")
    if config.get("required_paired_units") != 12 or config.get("calls_per_arm_unit") != 4:
        raise ValueError("Phase-5C unit/model-call count differs")
    if config.get("max_output_tokens_per_call") != 128:
        raise ValueError("Phase-5C output-token cap differs")
    if config.get("presentation_balance") != {
        "strategy_specialist_first": 6,
        "strategy_balanced_first": 6,
        "arm_retained_first": 6,
        "arm_reset_first": 6,
        "cross_count_each": 3,
    }:
        raise ValueError("Phase-5C presentation balance differs")
    if config.get("primary_metric") != "mission_success_rate":
        raise ValueError("Phase-5C primary metric differs")
    units = materialize_units(config)
    return {
        "units": units,
        "unit_map": {unit["unit_id"]: unit for unit in units},
        "config_digest": config_digest(config),
        "gate": dict(_mapping(config["advancement_gate"], "gate")),
        "epsilon": 1e-12,
        "source_capsule_sha256": _SOURCE_CAPSULE_SHA,
    }


def _validate_visible(record: Mapping[str, Any], arm: str, unit: Mapping[str, Any], epsilon: float) -> dict[str, Any]:
    visible = _mapping(record.get("model_visible"), "model_visible")
    serialized = json.dumps(visible, sort_keys=True)
    for skill in _REAL_SKILLS:
        if skill in serialized:
            raise ValueError("real skill name leaked into Phase-5C model-visible payload")
    if any(key in serialized for key in _PRIVATE_KEYS):
        raise ValueError("Phase-5C constructor answer key leaked into model-visible payload")
    memory = _mapping(visible.get("institutional_model_memory"), "institutional_model_memory")
    posterior = _mapping(memory.get("structural_posterior"), "structural_posterior")
    if set(posterior) != {"role_specific", "cross_coverage", "evidence_episodes"}:
        raise ValueError("Phase-5C posterior schema differs")
    role = posterior["role_specific"]
    cross = posterior["cross_coverage"]
    evidence = posterior["evidence_episodes"]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (role, cross)):
        raise ValueError("Phase-5C posterior probabilities must be numeric")
    if not isinstance(evidence, int) or isinstance(evidence, bool):
        raise ValueError("Phase-5C evidence count must be integer")
    if not math.isclose(float(role) + float(cross), 1.0, abs_tol=1e-9):
        raise ValueError("Phase-5C posterior must sum to one")
    if arm == "model_reset":
        if evidence != 0 or not math.isclose(float(role), 0.5, abs_tol=1e-12) or not math.isclose(float(cross), 0.5, abs_tol=1e-12):
            raise ValueError("Phase-5C reset arm must expose exact neutral prior")
    elif evidence != 192:
        raise ValueError("Phase-5C retained arm must expose 192 formation episodes")
    forecasts = _mapping(memory.get("current_roster_strategy_forecast"), "forecasts")
    preferred, margin = _preferred(forecasts)
    target = str(unit["target_hypothesis"])
    if target == "role_specific":
        posterior_target_match = float(role) > float(cross)
    elif target == "cross_coverage":
        posterior_target_match = float(cross) > float(role)
    else:
        raise ValueError("Phase-5C target hypothesis outside lock")
    return {
        "visible": dict(visible),
        "preferred": preferred,
        "margin": margin,
        "decisive": margin > epsilon,
        "posterior_target_match": posterior_target_match,
        "target_forecast_match": preferred == unit["target_policy"],
        "neutral_forecast_match": preferred == unit["neutral_preferred_policy"],
    }


def _validate_record(record: Mapping[str, Any], *, arm: str, unit: Mapping[str, Any], lock: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("schema") != _RECORD_SCHEMA or record.get("arm") != arm:
        raise ValueError("Phase-5C record schema/arm differs")
    if record.get("unit_id") != unit["unit_id"] or record.get("field_id") != unit["field_id"]:
        raise ValueError("Phase-5C unit/field identity differs")
    if record.get("trial_seed") != unit["trial_seed"]:
        raise ValueError("Phase-5C trial seed differs")
    if record.get("field_revision") != _FIELD_SHA or record.get("model_snapshot") != _MODEL:
        raise ValueError("Phase-5C record Field/model drift")
    if record.get("config_digest") != lock["config_digest"]:
        raise ValueError("Phase-5C record config digest differs")
    if tuple(record.get("strategy_order", ())) != tuple(unit["strategy_order"]):
        raise ValueError("Phase-5C strategy presentation differs")
    if record.get("arm_order_label") != unit["arm_order_label"]:
        raise ValueError("Phase-5C arm order differs")
    audit = _mapping(record.get("audit"), "audit")
    for key in ("hidden_regime", "target_hypothesis", "target_policy", "neutral_preferred_policy"):
        if audit.get(key) != unit[key]:
            raise ValueError(f"Phase-5C audit {key} differs from constructor lock")
    visible = _validate_visible(record, arm, unit, float(lock["epsilon"]))
    if audit.get("forecast_preferred_strategy") != visible["preferred"]:
        raise ValueError("Phase-5C runner forecast preference differs from analyzer")
    if not math.isclose(float(audit.get("forecast_margin", -1.0)), visible["margin"], abs_tol=1e-12):
        raise ValueError("Phase-5C runner forecast margin differs from analyzer")
    if audit.get("decisive_forecast") is not visible["decisive"]:
        raise ValueError("Phase-5C decisive-forecast flag differs")
    chosen = audit.get("chosen_strategy")
    intended = audit.get("intended_strategy")
    speech = audit.get("speech_strategy")
    if chosen not in _STRATEGIES or intended not in _STRATEGIES or speech not in _STRATEGIES:
        raise ValueError("Phase-5C strategy outside binary vocabulary")
    trials = audit.get("evaluation_trials")
    successes = audit.get("success_count")
    rate = audit.get("mission_success_rate")
    if trials != 256 or not isinstance(successes, int) or isinstance(successes, bool) or not 0 <= successes <= 256:
        raise ValueError("Phase-5C evaluation count differs")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isclose(float(rate), successes / 256.0, abs_tol=1e-12):
        raise ValueError("Phase-5C success rate inconsistent with registered trials")
    grounded = float(rate) >= 0.5
    if audit.get("grounded_success") is not grounded:
        raise ValueError("Phase-5C grounded-success flag differs")
    claims = audit.get("post_action_claims_success")
    if not isinstance(claims, bool):
        raise ValueError("Phase-5C claims_success must be boolean")
    usage = _mapping(record.get("usage"), "usage")
    if usage.get("calls") != 4:
        raise ValueError("Phase-5C requires exactly four logical calls")
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("Phase-5C token count malformed")
    latency = usage.get("latency_ms")
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or float(latency) < 0:
        raise ValueError("Phase-5C latency malformed")
    roster_digest = record.get("replacement_roster_digest")
    seed_digest = record.get("environment_trial_seed_digest")
    if not isinstance(roster_digest, str) or len(roster_digest) != 64:
        raise ValueError("Phase-5C roster digest malformed")
    if not isinstance(seed_digest, str) or len(seed_digest) != 64:
        raise ValueError("Phase-5C environment seed digest malformed")
    return {
        **visible,
        "success_rate": float(rate),
        "chosen": str(chosen),
        "forecast_fidelity": chosen == visible["preferred"],
        "contradiction": speech != chosen,
        "intent_divergence": intended != chosen,
        "report_mismatch": claims != grounded,
        "unsupported_success": claims and not grounded,
        "input_tokens": int(usage["input_tokens"]),
        "output_tokens": int(usage["output_tokens"]),
        "latency_ms": float(latency),
        "roster_digest": roster_digest,
        "seed_digest": seed_digest,
    }


def _arm_records(payload: Mapping[str, Any], arm: str, lock: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if payload.get("schema") != _PAYLOAD_SCHEMA or payload.get("arm") != arm:
        raise ValueError("Phase-5C arm payload schema/arm differs")
    if payload.get("field_revision") != _FIELD_SHA or payload.get("model_snapshot") != _MODEL:
        raise ValueError("Phase-5C arm payload Field/model drift")
    if payload.get("source_capsule_sha256") != _SOURCE_CAPSULE_SHA:
        raise ValueError("Phase-5C arm payload source differs")
    if payload.get("config_digest") != lock["config_digest"]:
        raise ValueError("Phase-5C arm payload config digest differs")
    records = _sequence(payload.get("records"), "records")
    if len(records) != 12:
        raise ValueError("Phase-5C arm payload must contain 12 records")
    result: dict[str, Mapping[str, Any]] = {}
    for raw in records:
        record = _mapping(raw, "record")
        unit_id = record.get("unit_id")
        if not isinstance(unit_id, str) or unit_id in result:
            raise ValueError("Phase-5C unit IDs must be unique strings")
        result[unit_id] = record
    if set(result) != set(lock["unit_map"]):
        raise ValueError("Phase-5C arm unit set differs from lock")
    return result


def analyze(config: Mapping[str, Any], reset_payload: Mapping[str, Any], retained_payload: Mapping[str, Any]) -> dict[str, Any]:
    lock = validate_config(config)
    raw = {
        "model_reset": _arm_records(reset_payload, "model_reset", lock),
        "model_retained": _arm_records(retained_payload, "model_retained", lock),
    }
    rows: dict[str, dict[str, dict[str, Any]]] = {arm: {} for arm in _ARMS}
    for unit in lock["units"]:
        unit_id = unit["unit_id"]
        for arm in _ARMS:
            rows[arm][unit_id] = _validate_record(raw[arm][unit_id], arm=arm, unit=unit, lock=lock)
        reset = rows["model_reset"][unit_id]
        retained = rows["model_retained"][unit_id]
        if reset["roster_digest"] != retained["roster_digest"]:
            raise ValueError("Phase-5C paired arms must share exact replacement roster")
        if reset["seed_digest"] != retained["seed_digest"]:
            raise ValueError("Phase-5C paired arms must share exact environment seeds")
        reset_visible = dict(reset["visible"])
        retained_visible = dict(retained["visible"])
        reset_memory = reset_visible.pop("institutional_model_memory")
        retained_memory = retained_visible.pop("institutional_model_memory")
        if reset_visible != retained_visible:
            raise ValueError("Phase-5C model-visible paired context differs outside memory")
        if reset_memory == retained_memory:
            raise ValueError("Phase-5C memory intervention unexpectedly identical")

    metrics: dict[str, dict[str, Any]] = {}
    for arm in _ARMS:
        arm_rows = list(rows[arm].values())
        decisive = [row for row in arm_rows if row["decisive"]]
        metrics[arm] = {
            "mission_success_rate": statistics.mean(row["success_rate"] for row in arm_rows),
            "decisive_forecast_units": len(decisive),
            "forecast_fidelity_rate": statistics.mean(float(row["forecast_fidelity"]) for row in decisive) if decisive else 0.0,
            "cross_channel_contradiction_rate": statistics.mean(float(row["contradiction"]) for row in arm_rows),
            "intent_action_divergence_rate": statistics.mean(float(row["intent_divergence"]) for row in arm_rows),
            "outcome_report_mismatch_rate": statistics.mean(float(row["report_mismatch"]) for row in arm_rows),
            "unsupported_success_claim_rate": statistics.mean(float(row["unsupported_success"]) for row in arm_rows),
            "mean_input_tokens": statistics.mean(row["input_tokens"] for row in arm_rows),
            "mean_output_tokens": statistics.mean(row["output_tokens"] for row in arm_rows),
            "mean_model_latency_ms": statistics.mean(row["latency_ms"] for row in arm_rows),
        }

    effects: list[float] = []
    better = worse = ties = 0
    nonnegative = 0
    reset_neutral_matches = 0
    retained_posterior_matches = 0
    retained_target_forecast_matches = 0
    forecast_changes = 0
    for unit in lock["units"]:
        unit_id = unit["unit_id"]
        reset = rows["model_reset"][unit_id]
        retained = rows["model_retained"][unit_id]
        effect = retained["success_rate"] - reset["success_rate"]
        effects.append(effect)
        nonnegative += int(effect >= 0.0)
        if effect > 0:
            better += 1
        elif effect < 0:
            worse += 1
        else:
            ties += 1
        reset_neutral_matches += int(reset["neutral_forecast_match"])
        retained_posterior_matches += int(retained["posterior_target_match"])
        retained_target_forecast_matches += int(retained["target_forecast_match"])
        forecast_changes += int(retained["preferred"] != reset["preferred"])
    mean_effect = statistics.mean(effects)
    sign_p = _exact_sign_test(better, worse)
    report_delta = metrics["model_retained"]["outcome_report_mismatch_rate"] - metrics["model_reset"]["outcome_report_mismatch_rate"]
    gate = lock["gate"]
    advance = (
        mean_effect >= float(gate["min_mean_retained_minus_reset_success_rate"])
        and sign_p <= float(gate["max_primary_sign_test_p"])
        and nonnegative >= int(gate["min_nonnegative_unit_effects"])
        and report_delta <= float(gate["max_outcome_report_mismatch_delta"])
        and reset_neutral_matches == int(gate["required_reset_neutral_forecast_match_units"])
        and retained_posterior_matches >= int(gate["min_retained_target_posterior_match_units"])
        and retained_target_forecast_matches >= int(gate["min_retained_target_forecast_match_units"])
        and forecast_changes >= int(gate["min_forecast_preference_change_units"])
        and all(metrics[arm]["decisive_forecast_units"] >= int(gate["min_decisive_forecast_units_each_arm"]) for arm in _ARMS)
        and all(metrics[arm]["forecast_fidelity_rate"] >= float(gate["min_forecast_fidelity_each_arm"]) for arm in _ARMS)
    )
    return {
        "experiment": _EXPERIMENT,
        "preregistration_revision": _REVISION,
        "scientific_interpretation_eligible": True,
        "capability_test_not_prevalence_estimate": True,
        "records_per_arm": 12,
        "paired_units": 12,
        "metrics": metrics,
        "primary": {
            "mean_retained_minus_reset_success_rate": mean_effect,
            "paired_better": better,
            "paired_worse": worse,
            "paired_ties": ties,
            "paired_discordant": better + worse,
            "exact_two_sided_sign_test_p": sign_p,
            "nonnegative_unit_effects": nonnegative,
        },
        "mechanism": {
            "reset_neutral_forecast_match_units": reset_neutral_matches,
            "retained_target_posterior_match_units": retained_posterior_matches,
            "retained_target_forecast_match_units": retained_target_forecast_matches,
            "forecast_preference_change_units": forecast_changes,
            "outcome_report_mismatch_delta": report_delta,
        },
        "advancement_gate": dict(gate),
        "advance_beyond_phase5c_decision_relevant_memory": advance,
        "config_digest": lock["config_digest"],
        "dataset_digest": _digest({"model_reset": reset_payload, "model_retained": retained_payload}),
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
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
