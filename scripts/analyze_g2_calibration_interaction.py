"""Exploratory interaction analysis on the G2 developmental calibration.

Owner mandate (2026-10-29): register the mechanism x environment
interaction on the calibration data AS EXPLORATORY, decomposing the
ITT difference into decision errors vs token-exhaustion (length)
failures per class; correct the stratified variance/power estimates;
ban the naive pooled N (287-690) as a final justification. Read-only
over the committed evidence; writes one canonical JSON report.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

EVIDENCE = Path("research/c3r_g2/evidence_g2_qualification_20261028")
CLASSES = ("unambiguous", "noisy_majority", "task_conditional")


def load_orgs() -> list[dict]:
    orgs = []
    for index in range(12):
        path = EVIDENCE / f"devcal-org-{index:02d}.json"
        orgs.append(json.loads(path.read_text(encoding="utf-8")))
    return orgs


def decompose_class(orgs: list[dict], cls: str) -> dict[str, object]:
    rows = [r for o in orgs if o["class"] == cls for r in o["rows"]]
    c_rows = [r for r in rows if r["arm"] == "C"]
    d_rows = [r for r in rows if r["arm"] == "D"]
    assert len(c_rows) == len(d_rows) == 64

    d_by_key = {(r["member"], r["task_id"]): r for r in d_rows}
    c_correct = sum(1 for r in c_rows if r["correct"])
    d_correct = sum(1 for r in d_rows if r["correct"])
    c_length = sum(
        1 for r in c_rows if r["classification"] == "length"
    )
    c_transport = sum(
        1 for r in c_rows if r["classification"] == "transport_error"
    )
    c_parseable = 64 - c_length - c_transport
    itt_diff = d_correct - c_correct

    # counterfactual upper bound: every C length-failure becomes correct
    c_best = c_correct + c_length
    diff_if_length_were_correct = d_correct - c_best

    # decision-only comparison on C-parseable cells (paired)
    paired_d_correct_on_parseable = 0
    for r in c_rows:
        if r["classification"] == "completed_parseable":
            d_row = d_by_key[(r["member"], r["task_id"])]
            if d_row["correct"]:
                paired_d_correct_on_parseable += 1
    decision_only_diff = paired_d_correct_on_parseable - c_correct

    return {
        "class": cls,
        "c_correct": c_correct, "d_correct": d_correct,
        "c_length_failures": c_length, "c_transport": c_transport,
        "c_parseable": c_parseable,
        "itt_diff": itt_diff,
        "itt_diff_pp": round(itt_diff / 64 * 100, 2),
        "diff_if_length_were_correct": diff_if_length_were_correct,
        "diff_if_length_were_correct_pp": round(
            diff_if_length_were_correct / 64 * 100, 2
        ),
        "decision_only_diff_on_parseable": decision_only_diff,
        "decision_only_diff_pp": round(decision_only_diff / 64 * 100, 2),
    }


def org_diffs(orgs: list[dict], cls: str) -> list[float]:
    out = []
    for o in orgs:
        if o["class"] != cls:
            continue
        c = o["per_arm"]["C"]["correct"]
        d = o["per_arm"]["D"]["correct"]
        out.append((d - c) / 16.0)
    return out


def main() -> int:
    orgs = load_orgs()
    decomposition = [decompose_class(orgs, cls) for cls in CLASSES]

    delta = {
        cls: statistics.mean(org_diffs(orgs, cls)) for cls in CLASSES
    }
    theta = delta["noisy_majority"] - delta["task_conditional"]

    # stratified SE (owner's formula), 4 orgs per class
    s = {cls: statistics.stdev(org_diffs(orgs, cls)) for cls in CLASSES}
    n = {cls: 4 for cls in CLASSES}
    w = {cls: 1 / 3 for cls in CLASSES}
    se_strat = math.sqrt(
        sum((w[c] ** 2) * (s[c] ** 2) / n[c] for c in CLASSES)
    )
    # naive pooled SE ignoring strata (12 orgs)
    pooled = [d for c in CLASSES for d in org_diffs(orgs, c)]
    sd_pooled = statistics.stdev(pooled)
    se_naive = sd_pooled / math.sqrt(12)

    # corrected power guidance for the joint gate (owner's rule:
    # assume a TRUE effect ABOVE the decision threshold; P(passage)
    # = P(significant AND estimate >= SESOI) ~ P(estimate >= SESOI)
    # for a one-sided test sized at the true effect)
    def n_for_gate(true_effect: float, se_target_factor: float = 1.0):
        # require P(estimate >= 0.05 | true) >= 0.8 with one-sided alpha
        z_alpha, z_beta = 1.645, 0.842
        # for the stratified mean with two informative strata (s=0.094):
        se_needed = (true_effect - 0.05) / z_beta
        n_per_class = (
            (s["noisy_majority"] ** 2 + s["task_conditional"] ** 2)
            / (9 * se_needed ** 2)
        )
        return math.ceil(n_per_class)

    power_guidance = {
        "rule": "assume true effect ABOVE the +5pp decision threshold; "
                "powering at exactly +5pp gives ~50% gate passage",
        "n_orgs_per_class_for_stratified_mean": {
            f"true_effect_{int(te * 100)}pp": n_for_gate(te)
            for te in (0.10, 0.15, 0.20)
        },
        "interaction_theta_se_at_4_per_class": math.sqrt(
            (s["noisy_majority"] ** 2 + s["task_conditional"] ** 2) / 4
        ),
        "note_interaction": "theta power depends on the NEW design's "
                            "environment parameter distributions, not on "
                            "these class-fixed SDs; the class-fixed sign is "
                            "pre-programmed by the compiler's granularity "
                            "and must not be re-confirmed expensively",
    }

    report = {
        "schema": "c3r-g2-calibration-exploratory-interaction-v0.1",
        "exploratory": True,
        "noninferential": True,
        "source_run": 40740553836,
        "class_deltas": {c: round(delta[c], 4) for c in CLASSES},
        "class_sds": {c: round(s[c], 4) for c in CLASSES},
        "interaction_theta_noisy_minus_conditional": round(theta, 4),
        "interaction_theta_pp": round(theta * 100, 2),
        "itt_decomposition": decomposition,
        "stratified_se_pp": round(se_strat * 100, 2),
        "naive_pooled_se_pp": round(se_naive * 100, 2),
        "pooled_sd_banned_for_final_n": True,
        "power_guidance": power_guidance,
        "scientific_acceptance": False,
    }
    out = EVIDENCE / "devcal-exploratory-interaction.json"
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
