"""Joint-gate power simulation for the G2 interaction estimand G (offline).

Owner directive (2026-10-29): the confirmatory gate is JOINT (positive
AND one-sided significant AND estimate >= SESOI). Significance-only N
understates the requirement; this simulation quantifies pass
probability as a function of N, true G, between-organization SD,
SESOI scenario, and C-class output-failure rates (which shift the
separate net-value condition D_VAR - C, not G). Deterministic Monte
Carlo (frozen seed); no model calls; conservative normal between-org
model with declared sensitivity; repeated tasks within an organization
are NEVER treated as independent units.

Also extracts, from the committed no-forced-sign report, the design
facts the owner required in the prereg: the seed-change decomposition
of the 10/20 band cells, and the region where D_VAR > D_CTX while
D_VAR still loses to C (representation precision without net value).
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

SCHEMA = "c3r-g2-joint-gate-power-v0.1"
SEED = 20261029
REPLICATES = 4000
N_GRID = list(range(12, 260, 4))
TRUE_GS = (0.10, 0.15, 0.20, 0.30)
SDS = (0.30, 0.45, 0.576, 0.70)
SESOI_SCENARIOS = (0.05, 0.10)
C_FAIL_RATES = (0.0, 0.09)
ALPHA_Z = 1.645
TARGET_POWER = 0.80
OUT = Path("research/c3r_g2/evidence_g2_qualification_20261028")


def gate_pass(observations: list[float], sesoi: float) -> bool:
    """Joint gate: positive mean AND one-sided significant AND >= SESOI."""

    n = len(observations)
    mean = statistics.mean(observations)
    if mean <= 0 or mean < sesoi:
        return False
    sd = statistics.stdev(observations)
    if sd == 0:
        return mean >= sesoi and mean > 0
    z = mean / (sd / (n ** 0.5))
    return z > ALPHA_Z


def pass_probability(true_g: float, sd: float, n: int, sesoi: float,
                     replicates: int = REPLICATES) -> float:
    rng = random.Random(f"{SEED}:{true_g}:{sd}:{n}:{sesoi}")
    hits = 0
    for _ in range(replicates):
        draws = [rng.gauss(true_g, sd) for _ in range(n)]
        if gate_pass(draws, sesoi):
            hits += 1
    return hits / replicates


def min_n_for_target(true_g: float, sd: float, sesoi: float) -> int | None:
    for n in N_GRID:
        if pass_probability(true_g, sd, n, sesoi) >= TARGET_POWER:
            return n
    return None


def significance_only_n(true_g: float, sd: float) -> float:
    return ((ALPHA_Z + 0.842) * sd / true_g) ** 2


def design_facts() -> dict[str, object]:
    report = json.loads(
        (OUT / "no-forced-sign-report.json").read_text(encoding="utf-8")
    )
    cells = report["cells"]
    band = [
        c for c in cells
        if c["beta"] in (0.15, 0.30) and c["gamma"] in (0.0, 0.2)
    ]
    decomposition: dict[str, int] = {}
    for cell in band:
        key = "+".join(sorted(cell["g_signs_across_seeds"]))
        decomposition[key] = decomposition.get(key, 0) + 1
    precision_without_value = [
        {"alpha": c["alpha"], "beta": c["beta"], "gamma": c["gamma"],
         "mean_g": round(c["mean_g"], 3),
         "mean_d_var_vs_c": round(c["mean_d_var"], 3)}
        for c in cells
        if c["mean_g"] > 0.05 and c["mean_d_var"] < -0.05
    ]
    return {
        "band_seed_change_decomposition": decomposition,
        "cells_where_D_VAR_beats_D_CTX_but_loses_to_C": (
            precision_without_value
        ),
        "note": "V1/V2 are grader-path sensitivity probes (oracle swap, "
                "corruption), not proof that the compiler derives correct "
                "knowledge from evidence; live developmental evidence "
                "(D_CTX 64/64 in the noisy class) is exploratory support "
                "for compiler correctness, recorded separately.",
    }


def net_value_condition(true_dvar_minus_c: float, sd: float, n: int,
                        c_fail: float, sesoi: float) -> float:
    """Pass probability for the SEPARATE net-value gate D_VAR - C.

    C output failures (~9% observed) shift the measured difference down
    by c_fail * P(cell would otherwise be correct) ~= c_fail * 0.85 and
    inflate variance; modeled as a mean shift with declared sensitivity.
    """

    shifted = true_dvar_minus_c - c_fail * 0.85
    return pass_probability(shifted, sd, n, sesoi)


def main() -> int:
    table = []
    for sesoi in SESOI_SCENARIOS:
        for sd in SDS:
            for true_g in TRUE_GS:
                n_joint = min_n_for_target(true_g, sd, sesoi)
                n_sig_only = significance_only_n(true_g, sd)
                table.append({
                    "sesoi_G": sesoi, "sd": sd, "true_G": true_g,
                    "N_joint_gate_80pct": n_joint,
                    "N_significance_only_approx": round(n_sig_only, 1),
                    "sends_at_N_joint": (
                        n_joint * 48 if n_joint is not None else None
                    ),
                })

    net_value = []
    for c_fail in C_FAIL_RATES:
        for true_net in (0.15, 0.25):
            net_value.append({
                "c_fail_rate": c_fail, "true_D_VAR_minus_C": true_net,
                "pass_prob_at_N60_sd0.45": round(
                    net_value_condition(true_net, 0.45, 60, c_fail, 0.05), 3
                ),
            })

    report = {
        "schema": SCHEMA,
        "frozen_seed": SEED,
        "replicates": REPLICATES,
        "gate": "positive AND one-sided z>1.645 AND estimate>=SESOI",
        "model": "org-level paired G ~ Normal(true_G, SD); between-org "
                 "variance only; repeated tasks never independent units",
        "N_grid": (N_GRID[0], N_GRID[-1], N_GRID[1] - N_GRID[0]),
        "joint_gate_table": table,
        "net_value_condition_sensitivity": net_value,
        "design_facts": design_facts(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "joint-gate-power-simulation.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(
        {
            "joint_gate_table(head)": table[:6],
            "net_value_condition_sensitivity": net_value,
            "design_facts": report["design_facts"],
        },
        indent=2, sort_keys=True,
    ))
    print(f"report written: {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
