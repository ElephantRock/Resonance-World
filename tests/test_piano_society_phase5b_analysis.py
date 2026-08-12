import copy
import hashlib
import json
from pathlib import Path

import pytest

from experiments.piano_society.phase5b import analyze, materialize_units, validate_config


CONFIG_PATH = Path("experiments/piano_society/phase5b_config.json")


def _config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _memory(arm: str):
    if arm == "model_reset":
        posterior = {
            "role_specific": 0.5,
            "cross_coverage": 0.5,
            "evidence_episodes": 0,
        }
        forecasts = {"specialist": 0.45, "balanced": 0.30}
    else:
        posterior = {
            "role_specific": 0.9,
            "cross_coverage": 0.1,
            "evidence_episodes": 192,
        }
        forecasts = {"specialist": 0.60, "balanced": 0.25}
    return {
        "structural_posterior": posterior,
        "current_roster_strategy_forecast": forecasts,
        "forecast_semantics": {
            "role_specific": "role competence",
            "cross_coverage": "cross-role coverage",
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
            successes = 64 if retained else 32
            rate = successes / 128.0
            by_arm[arm].append(
                {
                    "schema": "resonance-world-piano-phase5b-unit-v0.1",
                    "arm": arm,
                    "unit_id": unit["unit_id"],
                    "field_id": unit["field_id"],
                    "mission_id": unit["mission"]["mission_id"],
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
                            f"context={unit['mission']['context']}; "
                            f"lead_skill={unit['mission']['public_lead_skill']}; "
                            f"support_skill={unit['mission']['public_support_skill']}"
                        ),
                        "roster_text": '[{"member":"member-1","practice":{"skill-a":2}}]',
                        "institutional_model_memory": _memory(arm),
                    },
                    "audit": {
                        "hidden_regime": unit["mission"]["hidden_regime"],
                        "forecast_preferred_strategy": "specialist",
                        "forecast_margin": 0.35 if retained else 0.15,
                        "decisive_forecast": True,
                        "intention": "use the forecast",
                        "intended_strategy": "specialist",
                        "speech": "use specialist routing",
                        "speech_strategy": "specialist",
                        "chosen_strategy": "specialist",
                        "confidence": 0.9,
                        "evaluation_trials": 128,
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
            "schema": "resonance-world-piano-phase5b-arm-v0.1",
            "arm": arm,
            "field_revision": config["field_revision"],
            "model_snapshot": config["required_model_snapshot"],
            "source_capsule_sha256": config["source_lock"]["capsule_sha256"],
            "config_digest": lock["config_digest"],
            "records": records,
        }
    return config, payloads


def test_phase5b_locked_config_and_complete_synthetic_gate() -> None:
    config, payloads = _payloads()
    result = analyze(config, payloads["model_reset"], payloads["model_retained"])
    assert result["scientific_interpretation_eligible"] is True
    assert result["records_per_arm"] == 24
    assert result["primary"]["mean_retained_minus_reset_success_rate"] == 0.25
    assert result["primary"]["paired_better"] == 24
    assert result["primary"]["paired_worse"] == 0
    assert result["metrics"]["model_reset"]["forecast_fidelity_rate"] == 1.0
    assert result["metrics"]["model_retained"]["forecast_fidelity_rate"] == 1.0
    assert result["advance_beyond_phase5b_transferable_memory"] is True


def test_phase5b_rejects_non_neutral_reset_prior() -> None:
    config, payloads = _payloads()
    broken = copy.deepcopy(payloads["model_reset"])
    broken["records"][0]["model_visible"]["institutional_model_memory"][
        "structural_posterior"
    ]["role_specific"] = 0.6
    broken["records"][0]["model_visible"]["institutional_model_memory"][
        "structural_posterior"
    ]["cross_coverage"] = 0.4
    with pytest.raises(ValueError, match="neutral prior"):
        analyze(config, broken, payloads["model_retained"])


def test_phase5b_rejects_pair_roster_drift() -> None:
    config, payloads = _payloads()
    broken = copy.deepcopy(payloads["model_retained"])
    broken["records"][0]["replacement_roster_digest"] = "b" * 64
    with pytest.raises(ValueError, match="exact replacement roster"):
        analyze(config, payloads["model_reset"], broken)


def test_phase5b_rejects_real_skill_leakage() -> None:
    config, payloads = _payloads()
    broken = copy.deepcopy(payloads["model_retained"])
    broken["records"][0]["model_visible"]["mission_text"] += "; urban_heat"
    with pytest.raises(ValueError, match="real skill name leaked"):
        analyze(config, payloads["model_reset"], broken)
