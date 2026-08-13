import copy
import hashlib
import json
from pathlib import Path

import pytest

from experiments.piano_society.phase5c import analyze, materialize_units, validate_config

_CONFIG = Path("experiments/piano_society/phase5c_config.json")


def _config():
    return json.loads(_CONFIG.read_text(encoding="utf-8"))


def _forecasts(preferred: str):
    other = "balanced" if preferred == "specialist" else "specialist"
    return {preferred: 0.6, other: 0.4}


def _memory(arm: str, unit):
    if arm == "model_reset":
        posterior = {"role_specific": 0.5, "cross_coverage": 0.5, "evidence_episodes": 0}
        preferred = unit["neutral_preferred_policy"]
    else:
        if unit["target_hypothesis"] == "role_specific":
            posterior = {"role_specific": 0.9, "cross_coverage": 0.1, "evidence_episodes": 192}
        else:
            posterior = {"role_specific": 0.1, "cross_coverage": 0.9, "evidence_episodes": 192}
        preferred = unit["target_policy"]
    return {
        "structural_posterior": posterior,
        "current_roster_strategy_forecast": _forecasts(preferred),
        "forecast_semantics": {
            "role_specific": "distinct role competence",
            "cross_coverage": "joint cross-role coverage",
        },
    }


def _payloads():
    config = _config()
    lock = validate_config(config)
    by_arm = {"model_reset": [], "model_retained": []}
    for unit in materialize_units(config):
        seed_digest = hashlib.sha256(unit["unit_id"].encode()).hexdigest()
        for arm in by_arm:
            retained = arm == "model_retained"
            successes = 128 if retained else 64
            rate = successes / 256.0
            preferred = unit["target_policy"] if retained else unit["neutral_preferred_policy"]
            memory = _memory(arm, unit)
            by_arm[arm].append(
                {
                    "schema": "resonance-world-piano-phase5c-unit-v0.1",
                    "arm": arm,
                    "unit_id": unit["unit_id"],
                    "field_id": unit["field_id"],
                    "trial_seed": unit["trial_seed"],
                    "field_revision": config["field_revision"],
                    "model_snapshot": config["required_model_snapshot"],
                    "config_digest": lock["config_digest"],
                    "strategy_order": list(unit["strategy_order"]),
                    "arm_order_label": unit["arm_order_label"],
                    "replacement_roster_digest": "a" * 64,
                    "environment_trial_seed_digest": seed_digest,
                    "model_visible": {
                        "mission_text": (
                            f"context={unit['unit_id']}; lead_skill={unit['public_lead_skill']}; "
                            f"support_skill={unit['public_support_skill']}"
                        ),
                        "roster_text": '[{"member":"member-1","practice":{"skill-a":2}}]',
                        "institutional_model_memory": memory,
                    },
                    "audit": {
                        "hidden_regime": unit["hidden_regime"],
                        "target_hypothesis": unit["target_hypothesis"],
                        "target_policy": unit["target_policy"],
                        "neutral_preferred_policy": unit["neutral_preferred_policy"],
                        "forecast_preferred_strategy": preferred,
                        "forecast_margin": 0.2,
                        "decisive_forecast": True,
                        "intention": "follow the institution forecast",
                        "intended_strategy": preferred,
                        "speech": f"use {preferred} routing",
                        "speech_strategy": preferred,
                        "chosen_strategy": preferred,
                        "confidence": 0.9,
                        "evaluation_trials": 256,
                        "success_count": successes,
                        "mission_success_rate": rate,
                        "grounded_success": retained,
                        "post_action_report": "registered evaluation complete",
                        "post_action_claims_success": retained,
                        "environment_reads_memory": False,
                        "evaluation_updates_memory": False,
                    },
                    "usage": {
                        "calls": 4,
                        "input_tokens": 40,
                        "output_tokens": 20,
                        "latency_ms": 8.0,
                    },
                }
            )
    payloads = {}
    for arm, records in by_arm.items():
        payloads[arm] = {
            "schema": "resonance-world-piano-phase5c-arm-v0.1",
            "arm": arm,
            "field_revision": config["field_revision"],
            "model_snapshot": config["required_model_snapshot"],
            "source_capsule_sha256": config["source_lock"]["capsule_sha256"],
            "config_digest": lock["config_digest"],
            "records": records,
        }
    return config, payloads


def test_phase5c_complete_synthetic_gate_advances() -> None:
    config, payloads = _payloads()
    result = analyze(config, payloads["model_reset"], payloads["model_retained"])
    assert result["scientific_interpretation_eligible"] is True
    assert result["capability_test_not_prevalence_estimate"] is True
    assert result["records_per_arm"] == 12
    assert result["primary"]["mean_retained_minus_reset_success_rate"] == 0.25
    assert result["primary"]["paired_better"] == 12
    assert result["primary"]["paired_worse"] == 0
    assert result["primary"]["nonnegative_unit_effects"] == 12
    assert result["mechanism"]["reset_neutral_forecast_match_units"] == 12
    assert result["mechanism"]["retained_target_posterior_match_units"] == 12
    assert result["mechanism"]["retained_target_forecast_match_units"] == 12
    assert result["mechanism"]["forecast_preference_change_units"] == 12
    assert result["metrics"]["model_reset"]["forecast_fidelity_rate"] == 1.0
    assert result["metrics"]["model_retained"]["forecast_fidelity_rate"] == 1.0
    assert result["advance_beyond_phase5c_decision_relevant_memory"] is True


def test_phase5c_rejects_non_neutral_reset_prior() -> None:
    config, payloads = _payloads()
    broken = copy.deepcopy(payloads["model_reset"])
    posterior = broken["records"][0]["model_visible"]["institutional_model_memory"]["structural_posterior"]
    posterior["role_specific"] = 0.6
    posterior["cross_coverage"] = 0.4
    with pytest.raises(ValueError, match="exact neutral prior"):
        analyze(config, broken, payloads["model_retained"])


def test_phase5c_rejects_constructor_answer_key_leakage() -> None:
    config, payloads = _payloads()
    broken = copy.deepcopy(payloads["model_retained"])
    broken["records"][0]["model_visible"]["target_policy"] = "specialist"
    with pytest.raises(ValueError, match="answer key leaked"):
        analyze(config, payloads["model_reset"], broken)


def test_phase5c_rejects_real_skill_leakage() -> None:
    config, payloads = _payloads()
    broken = copy.deepcopy(payloads["model_retained"])
    broken["records"][0]["model_visible"]["mission_text"] += "; urban_heat"
    with pytest.raises(ValueError, match="real skill name leaked"):
        analyze(config, payloads["model_reset"], broken)


def test_phase5c_rejects_pair_roster_drift() -> None:
    config, payloads = _payloads()
    broken = copy.deepcopy(payloads["model_retained"])
    broken["records"][0]["replacement_roster_digest"] = "b" * 64
    with pytest.raises(ValueError, match="exact replacement roster"):
        analyze(config, payloads["model_reset"], broken)
