import json
from pathlib import Path

from resonance.experiments.piano_phase2 import ModelRequest
from resonance_world.w4a_joint_learning import IndividualState

from experiments.piano_society.phase3 import config_digest
from experiments.piano_society.phase5 import analyze, materialize_units, validate_config
from experiments.piano_society.phase5_campaign import _memory_text, _mission_text, _roster_views
from experiments.piano_society.phase5_zai import Phase5ZAIChatCompletionsBackend


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase5_config.json").read_text())


def _stats():
    return {
        "specialist": {"attempts": 48, "successes": 36, "rate": 0.75},
        "balanced": {"attempts": 48, "successes": 24, "rate": 0.5},
    }


def _record(unit, *, arm: str, success_count: int, selected_strategy: str):
    mission = unit["mission"]
    stats = _stats()
    rate = success_count / 128.0
    grounded = rate >= 0.5
    mission_text = (
        f"context={mission['context']}; lead_skill={mission['public_lead_skill']}; "
        f"support_skill={mission['public_support_skill']}"
    )
    roster_text = json.dumps(
        [
            {
                "member": "member-0",
                "practice": {
                    "skill-a": 1,
                    "skill-b": 2,
                    "skill-c": 3,
                    "skill-d": 4,
                    "skill-e": 5,
                    "skill-f": 6,
                },
            },
            {
                "member": "member-1",
                "practice": {
                    "skill-a": 6,
                    "skill-b": 5,
                    "skill-c": 4,
                    "skill-d": 3,
                    "skill-e": 2,
                    "skill-f": 1,
                },
            },
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    memory_text = _memory_text(stats, arm)
    return {
        "schema": "resonance-world-piano-phase5-memory-unit-v0.1",
        "arm": arm,
        "unit_id": unit["unit_id"],
        "field_id": unit["field_id"],
        "mission_id": mission["mission_id"],
        "trial_seed": unit["trial_seed"],
        "model_snapshot": "glm-5.2",
        "strategy_order": list(unit["strategy_order"]),
        "strategy_order_label": unit["strategy_order_label"],
        "arm_order_label": unit["arm_order_label"],
        "intention": f"Use {selected_strategy} routing.",
        "intended_strategy": selected_strategy,
        "speech": f"The organization will use {selected_strategy} routing.",
        "speech_strategy": selected_strategy,
        "selected_strategy": selected_strategy,
        "confidence": 0.8,
        "selected_lead_member": "member-0",
        "selected_support_member": "member-1",
        "roster_digest": "a" * 64,
        "environment_seed_digest": "b" * 64,
        "evaluation_trials": 128,
        "success_count": success_count,
        "mission_success_rate": rate,
        "grounded_success": grounded,
        "post_action_report": "Audited evaluation reported.",
        "post_action_claims_success": grounded,
        "historical_best_strategy": "specialist",
        "model_visible": {
            "mission_text": mission_text,
            "roster_text": roster_text,
            "memory_text": memory_text,
        },
        "audit": {
            "historical_strategy_stats": stats,
            "hidden_regime": mission["hidden_regime"],
            "real_lead_skill": mission["lead_skill"],
            "real_support_skill": mission["support_skill"],
            "evaluation_updates_memory": False,
            "environment_reads_memory": False,
        },
        "usage": {
            "calls": 4,
            "input_tokens": 40,
            "output_tokens": 20,
            "latency_ms": 8.0,
        },
    }


def _payload(config, units, *, arm: str, success_count: int, selected_strategy: str):
    return {
        "schema": "resonance-world-piano-phase5-memory-arm-v0.1",
        "arm": arm,
        "field_revision": config["field_revision"],
        "source_capsule_sha256": config["source_lock"]["capsule_sha256"],
        "config_digest": config_digest(config),
        "records": [
            _record(
                unit,
                arm=arm,
                success_count=success_count,
                selected_strategy=selected_strategy,
            )
            for unit in units
        ],
    }


def test_phase5_lock_materializes_exact_counterbalanced_units() -> None:
    config = _config()
    normalized = validate_config(config)
    units = normalized["units"]

    assert len(units) == 24
    assert sum(unit["strategy_order_label"] == "specialist_first" for unit in units) == 12
    assert sum(unit["strategy_order_label"] == "balanced_first" for unit in units) == 12
    assert sum(unit["arm_order_label"] == "memory_retained_first" for unit in units) == 12
    assert sum(unit["arm_order_label"] == "memory_reset_first" for unit in units) == 12
    cross = {
        (strategy, arm): sum(
            unit["strategy_order_label"] == strategy and unit["arm_order_label"] == arm
            for unit in units
        )
        for strategy in ("specialist_first", "balanced_first")
        for arm in ("memory_retained_first", "memory_reset_first")
    }
    assert set(cross.values()) == {6}
    assert config["provider_format_template"]["action_example_source"] == (
        "first_registered_strategy"
    )


def test_phase5_model_visible_context_blinds_real_skills_ids_and_memory_label() -> None:
    config = _config()
    mission = config["missions"][0]
    mission_text = _mission_text(mission)
    aliases = config["skill_aliases"]
    roster = [
        IndividualState("uuid-a", {skill: index for index, skill in enumerate(aliases, 1)}),
        IndividualState("uuid-b", {skill: index + 2 for index, skill in enumerate(aliases, 1)}),
    ]
    roster_text, _, _ = _roster_views(roster, aliases)
    retained = _memory_text(_stats(), "memory_retained")
    reset = _memory_text(_stats(), "memory_reset")
    combined = "\n".join((mission_text, roster_text, retained, reset)).lower()

    assert "uuid-" not in combined
    assert "w4-source-seed" not in combined
    assert "hidden_regime" not in combined
    assert "historical_best" not in combined
    for real_skill in aliases:
        assert real_skill not in combined
    assert set(json.loads(retained)) == {"specialist", "balanced"}
    assert json.loads(reset) == {
        "balanced": {"attempts": 0, "rate": None, "successes": 0},
        "specialist": {"attempts": 0, "rate": None, "successes": 0},
    }


def test_phase5_zai_format_example_uses_registered_strategy_not_observe() -> None:
    backend = Phase5ZAIChatCompletionsBackend(
        api_key="test-key",
        model_snapshot="glm-5.2",
        allowed_actions=("balanced", "specialist"),
        retry_contract_errors=True,
        contract_retry_prompt_hardening=True,
        unique_request_id_per_attempt=True,
    )
    body = backend.request_body(
        ModelRequest(
            stage="action",
            prompt="Choose a routing strategy.",
            seed=950001,
            max_output_tokens=128,
        )
    )
    system = body["messages"][0]["content"]

    assert '"action":"balanced"' in system
    assert "OBSERVE" not in system
    assert "balanced, specialist" in system


def test_phase5_analyzer_advances_only_on_frozen_paired_gate() -> None:
    config = _config()
    units = materialize_units(config)
    reset = _payload(
        config,
        units,
        arm="memory_reset",
        success_count=40,
        selected_strategy="balanced",
    )
    retained = _payload(
        config,
        units,
        arm="memory_retained",
        success_count=80,
        selected_strategy="specialist",
    )

    result = analyze(config, reset, retained)

    assert result["delta_retained_minus_reset"]["mission_success_rate"] == 40 / 128
    assert result["primary_exact_sign_test"]["better"] == 24
    assert result["primary_exact_sign_test"]["worse"] == 0
    assert result["nonnegative_field_effects"] == 6
    assert result["advance_beyond_phase5_institutional_memory"] is True

    tied = _payload(
        config,
        units,
        arm="memory_retained",
        success_count=40,
        selected_strategy="specialist",
    )
    tied_result = analyze(config, reset, tied)
    assert tied_result["delta_retained_minus_reset"]["mission_success_rate"] == 0.0
    assert tied_result["primary_exact_sign_test"]["discordant_units"] == 0
    assert tied_result["advance_beyond_phase5_institutional_memory"] is False
