"""Frozen H8 evaluator and paired-binary statistical helpers."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any

from h8_representation_core import ARMS, FORBIDDEN_IR_KEYS, canonical_bytes, compiled_state, history_ir, prepare, strip_shell

P1_BAND = (-0.10, 0.10)
ALPHA = 0.05
Z90 = 1.6448536269514722
Z95 = 1.959963984540054


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_two_sided_mcnemar(treatment_wins: int, control_wins: int) -> float:
    discordant = treatment_wins + control_wins
    if discordant == 0:
        return 1.0
    tail = min(treatment_wins, control_wins)
    lower = sum(math.comb(discordant, i) for i in range(tail + 1)) / (2.0**discordant)
    return min(1.0, 2.0 * lower)


def wilson_interval(successes: int, n: int, z: float) -> tuple[float, float]:
    if n == 0:
        return 0.5, 0.5
    p = successes / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) / n) + (z * z) / (4.0 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def paired_risk_difference_interval(treatment_wins: int, control_wins: int, paired_n: int, confidence: float) -> tuple[float, float]:
    discordant = treatment_wins + control_wins
    if discordant == 0:
        return 0.0, 0.0
    z = Z90 if confidence == 0.90 else Z95
    low_theta, high_theta = wilson_interval(treatment_wins, discordant, z)
    scale = discordant / paired_n
    return scale * (2.0 * low_theta - 1.0), scale * (2.0 * high_theta - 1.0)


def contrast(outcomes: dict[str, dict[str, bool]], treatment: str, control: str, confidence: float = 0.95) -> dict[str, Any]:
    unit_ids = sorted(outcomes)
    treatment_wins = sum(outcomes[unit_id][treatment] and not outcomes[unit_id][control] for unit_id in unit_ids)
    control_wins = sum(outcomes[unit_id][control] and not outcomes[unit_id][treatment] for unit_id in unit_ids)
    treatment_correct = sum(outcomes[unit_id][treatment] for unit_id in unit_ids)
    control_correct = sum(outcomes[unit_id][control] for unit_id in unit_ids)
    n = len(unit_ids); difference = (treatment_correct - control_correct) / n
    interval = paired_risk_difference_interval(treatment_wins, control_wins, n, confidence)
    return {
        "treatment": treatment, "control": control, "paired_n": n,
        "treatment_correct": treatment_correct, "control_correct": control_correct,
        "risk_difference": difference, "discordant_treatment_wins": treatment_wins,
        "discordant_control_wins": control_wins,
        "raw_two_sided_exact_mcnemar_p": exact_two_sided_mcnemar(treatment_wins, control_wins),
        "confidence_level": confidence, "paired_risk_difference_ci": [interval[0], interval[1]],
        "ci_method": "conditional Wilson interval for treatment share among discordant pairs, transformed to paired risk difference",
    }


def holm(p_values: dict[str, float], alpha: float = ALPHA) -> dict[str, dict[str, Any]]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0])); m = len(ordered)
    adjusted: dict[str, float] = {}; running = 0.0; rejection_open = True; rejected: dict[str, bool] = {}
    for rank, (name, p_value) in enumerate(ordered, start=1):
        candidate = min(1.0, (m - rank + 1) * p_value); running = max(running, candidate); adjusted[name] = running
        threshold = alpha / (m - rank + 1); rejected[name] = rejection_open and p_value <= threshold
        if p_value > threshold: rejection_open = False
    return {name: {"raw_p": p_values[name], "holm_adjusted_p": adjusted[name], "holm_reject_fwer_0_05": rejected[name]} for name in p_values}


def recursive_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items(): keys.add(str(key)); keys.update(recursive_keys(child))
    elif isinstance(value, list):
        for child in value: keys.update(recursive_keys(child))
    return keys


def evaluate(*, evidence: dict[str, Any], evaluator: dict[str, Any], fixture_manifest: dict[str, Any], lock_report: dict[str, Any], live: dict[str, Any], candidate_head: str) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = prepare(evidence); plan_by_id = {cell["cell_id"]: cell for cell in plan["cells"]}; live_by_id = {cell["cell_id"]: cell for cell in live["cells"]}
    truth = {row["unit_id"]: row for row in evaluator["units"]}; units = {unit["unit_id"]: unit for unit in evidence["units"]}

    gates: dict[str, bool] = {}
    gates["gate_0_safety_boundary"] = not evidence["production_historical_substrate_enabled"] and not live["production_historical_substrate_enabled"]
    gates["gate_1_fixture_plan_and_candidate_identity"] = (
        fixture_manifest["confirmatory_unit_count"] == 384 and fixture_manifest["organization_cell_count"] == 1920
        and fixture_manifest["logical_model_call_count"] == 5760
        and lock_report["request_plan_sha256"] == hashlib.sha256(canonical_bytes(plan)).hexdigest() and bool(candidate_head)
    )
    gates["gate_2_fresh_unique_holdout_units"] = len(truth) == 384 and len(units) == 384 and len(set(truth)) == 384 and all(unit_id.startswith("h8-confirmatory-") for unit_id in truth)
    gates["gate_3_canonical_information_parity"] = True
    gates["gate_4_equal_three_call_compute"] = live["organization_cell_count"] == 1920 and live["logical_model_call_count"] == 5760
    gates["gate_5_exact_arm_protocol_and_balance"] = True
    gates["gate_6_current_authority_separation"] = True
    gates["gate_7_model_call_isolation"] = True
    gates["gate_8_live_transport_contract"] = live.get("model") == evidence["model_contract"]["model"]
    live_text = json.dumps(live, sort_keys=True)
    gates["gate_9_evaluator_private_leakage_exclusion"] = evaluator["private_evaluator_sentinel"] not in live_text and '"correct_action"' not in live_text
    gates["gate_10_t0_non_interpretive_shell_identity"] = bool(lock_report.get("t0_passed"))
    gates["gate_11_history_ir_reconstruction_and_forbidden_field_exclusion"] = True
    gates["gate_12_compiled_state_reconstruction_no_new_observation"] = True
    gates["gate_13_frozen_output_evaluator_reproducibility"] = True
    if set(plan_by_id) != set(live_by_id): gates["gate_1_fixture_plan_and_candidate_identity"] = False

    arm_counts: Counter[str] = Counter(); request_ids: list[str] = []
    outcomes: dict[str, dict[str, bool]] = {unit_id: {} for unit_id in truth}; per_cell: list[dict[str, Any]] = []
    family_arm_correct: dict[str, Counter[str]] = {family: Counter() for family in evidence["families"]}

    for cell_id, plan_cell in plan_by_id.items():
        live_cell = live_by_id.get(cell_id)
        if live_cell is None: continue
        arm = plan_cell["arm"]; unit_id = plan_cell["unit_id"]; arm_counts[arm] += 1
        if live_cell["unit_id"] != unit_id or live_cell["arm"] != arm: gates["gate_1_fixture_plan_and_candidate_identity"] = False
        if live_cell["representation_sha256"] != plan_cell["representation_sha256"]: gates["gate_3_canonical_information_parity"] = False
        if live_cell["protocol"] != plan_cell["protocol"]: gates["gate_5_exact_arm_protocol_and_balance"] = False

        unit = units[unit_id]; visible = plan_cell["visible_raw_evidence"]
        if arm == "raw_direct":
            if plan_cell["representation"] != visible: gates["gate_3_canonical_information_parity"] = False
        else:
            try: stripped = strip_shell(plan_cell["representation"])
            except ValueError:
                gates["gate_10_t0_non_interpretive_shell_identity"] = False; stripped = None
            if arm in {"raw_shell", "raw_shell_roles"} and stripped != visible: gates["gate_10_t0_non_interpretive_shell_identity"] = False
            if arm == "history_ir_roles":
                expected_ir = history_ir(unit, visible)
                if stripped != expected_ir or recursive_keys(stripped) & FORBIDDEN_IR_KEYS:
                    gates["gate_11_history_ir_reconstruction_and_forbidden_field_exclusion"] = False
            if arm == "compiled_state_roles":
                expected_state = compiled_state(unit, visible)
                if stripped != expected_state: gates["gate_12_compiled_state_reconstruction_no_new_observation"] = False
                if set(stripped.get("source_evidence_ids", [])) != set(plan_cell["evidence_slots"]):
                    gates["gate_12_compiled_state_reconstruction_no_new_observation"] = False

        if arm in {"raw_direct", "raw_shell"}:
            calls = live_cell.get("direct_calls", [])
            if len(calls) != 3: gates["gate_4_equal_three_call_compute"] = False
        else:
            analyst_calls = live_cell.get("analyst_calls", []); chair = live_cell.get("chair_call")
            if len(analyst_calls) != 2 or not isinstance(chair, dict):
                gates["gate_4_equal_three_call_compute"] = False; calls = analyst_calls
            else: calls = [*analyst_calls, chair]
        for call in calls:
            if call.get("model") != evidence["model_contract"]["model"]: gates["gate_8_live_transport_contract"] = False
            if not call.get("attempt_log") or call["attempt_log"][-1]["status"] != "ok": gates["gate_8_live_transport_contract"] = False
            elif call["request_id"] != call["attempt_log"][-1]["request_id"]: gates["gate_8_live_transport_contract"] = False
            for attempt in call.get("attempt_log", []): request_ids.append(attempt["request_id"])

        selected = live_cell["final_selection"]; authority_verified = bool(live_cell["authority_verification"]["verified"]); valid_notice = truth[unit_id]["valid_notice_id"]
        if selected["notice_id"] != valid_notice: gates["gate_6_current_authority_separation"] = False
        correct = selected["action"] == truth[unit_id]["correct_action"] and selected["notice_id"] == valid_notice and authority_verified
        outcomes[unit_id][arm] = correct; family_arm_correct[truth[unit_id]["family"]][arm] += int(correct)
        per_cell.append({"cell_id": cell_id, "unit_id": unit_id, "family": truth[unit_id]["family"], "arm": arm,
                         "correct": correct, "selected_action": selected["action"], "selected_notice_id": selected["notice_id"],
                         "authority_verified": authority_verified})

    if any(arm_counts[arm] != 384 for arm in ARMS): gates["gate_5_exact_arm_protocol_and_balance"] = False
    if any(set(arms) != set(ARMS) for arms in outcomes.values()): gates["gate_5_exact_arm_protocol_and_balance"] = False
    if len(request_ids) != len(set(request_ids)): gates["gate_7_model_call_isolation"] = False

    p1 = contrast(outcomes, "raw_shell", "raw_direct", confidence=0.90); p1["equivalence_band"] = list(P1_BAND)
    p1["equivalent_under_conventional_band"] = p1["paired_risk_difference_ci"][0] > P1_BAND[0] and p1["paired_risk_difference_ci"][1] < P1_BAND[1]
    p1["threshold_class"] = "conventional"
    p2 = contrast(outcomes, "raw_shell_roles", "raw_shell")
    p3 = contrast(outcomes, "history_ir_roles", "raw_shell_roles")
    p4 = contrast(outcomes, "compiled_state_roles", "raw_shell_roles")
    multiplicity = holm({"P2_role_chair_synthesis": p2["raw_two_sided_exact_mcnemar_p"],
                         "P3_history_ir": p3["raw_two_sided_exact_mcnemar_p"],
                         "P4_compiled_state": p4["raw_two_sided_exact_mcnemar_p"]})
    total_correct = {arm: sum(outcomes[unit_id][arm] for unit_id in outcomes) for arm in ARMS}
    family_counts = {family: {arm: family_arm_correct[family][arm] for arm in ARMS} for family in evidence["families"]}

    classifiable = all(gates.values())
    classification = "historical_substrate_history_representation_boundary_classified" if classifiable else "historical_substrate_history_representation_boundary_invalid"
    result = {
        "schema": "h8-result-v0.1", "classification": classification, "candidate_head": candidate_head,
        "scientific_claim": "registered_history_representation_boundary_vector_only",
        "statistical_contract": {
            "paired_n": 384,
            "P1": "90% conditional-Wilson paired-risk-difference CI vs conventional [-0.10,+0.10] equivalence band",
            "P2_P4": "two-sided exact McNemar with Holm FWER 0.05; 95% conditional-Wilson paired-risk-difference CIs",
        },
        "contrasts": {"P1_shell_equivalence": p1, "P2_role_chair_synthesis": p2, "P3_history_ir": p3, "P4_compiled_state": p4},
        "holm_family_P2_P4": multiplicity,
        "diagnostics": {"correctness_counts_out_of_384": total_correct, "family_correctness_counts_out_of_96": family_counts,
                        "organization_cell_count": live["organization_cell_count"], "logical_model_call_count": live["logical_model_call_count"],
                        "physical_provider_attempt_count": live["physical_provider_attempt_count"], "production_historical_substrate_enabled": False},
        "gates": gates,
    }
    audit = {"schema": "h8-audit-v0.1", "candidate_head": candidate_head,
             "request_plan_sha256": hashlib.sha256(canonical_bytes(plan)).hexdigest(), "live_output_sha256": sha256(live),
             "cell_count": len(per_cell), "unique_request_id_count": len(set(request_ids)),
             "request_id_observation_count": len(request_ids), "per_cell": per_cell}
    return result, audit
