"""G2 no-forced-sign check — ONE deterministic offline attempt (frozen spec).

Owner GO (2026-10-29): prove, without any model call, that the G2
interaction apparatus (a) MEASURES real granularity-driven performance
change (apparatus causal validity - must be POSITIVE) and (b) is NOT
fully generator-determined (the winner must not be pre-programmed by
the generator/compiler rules - must be NON-DEFINITIVE). If either
fails, the design CLOSES with zero sends; the grid is NOT iterated
until success.

FROZEN SPEC (declared before execution; no tuning after seeing output):
- Grid: alpha in {0.55,0.65,0.75,0.85,1.0} (evidence consistency),
  beta in {0.0,0.15,0.30,0.5} (deviation rate), gamma in {0.0,0.2,0.4}
  (TAG MASKING RATE - probability a record's variant tag is masked).
  60 cells; 5 independent seeds per cell = 300 environments.
- Environment: 20 records, 8 tasks, 2 members; per-variant truth drawn
  by seed (deviating variants get the opposite plan); a record is
  truthful (correct plan, success) with prob alpha, else misleading
  (wrong plan, success); tags masked iid with prob gamma.
- Compilers: D_CTX pools ALL records (context level; support floor 8,
  margin 2, abstain -> neutral). D_VAR pools UNMASKED records per
  variant (support floor 4, margin 1; per-variant abstention falls
  back to the D_CTX procedure; if that abstains too -> neutral).
- Idealized C: per (member, task) harness-matched sample of K=6 from
  the task-variant's UNMASKED records (pad from the context pool if
  fewer than 3); majority among successes; tie -> neutral.
- Per environment: mean over 16 (member, task) cells of correct; the
  estimands are D_CTX-C, D_VAR-C and G = D_VAR - D_CTX. Winner margin
  tau = 0.05.
- Validity probes: V1 oracle-granularity swap (D_VAR <- true per-
  variant plans) must lift D_VAR to ceiling exactly where information
  exists; V2 corruption swap (D_CTX plan flipped) must collapse D_CTX.
- Pre-declared analysis band: beta in {0.15,0.30} x gamma in {0.0,0.2}.
- A-priori rule predictions (for the determinism analysis ONLY):
  beta=0 -> G ~ 0; alpha=1.0 & gamma=0 -> G > 0 rule-predicted; else
  evidence-determined (live experiment informative there).
"""

from __future__ import annotations

import hashlib
import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "c3r-g2-no-forced-sign-v0.1"
SEED_DOMAIN = "g2-nfs-v1"
ALPHAS = (0.55, 0.65, 0.75, 0.85, 1.0)
BETAS = (0.0, 0.15, 0.30, 0.5)
GAMMAS = (0.0, 0.2, 0.4)
SEEDS_PER_CELL = 5
CORPUS = 20
TASKS = 8
MEMBERS = 2
K_SAMPLE = 6
CTX_FLOOR, CTX_MARGIN = 8, 2
VAR_FLOOR, VAR_MARGIN = 4, 1
TAU = 0.05
BAND_BETAS = (0.15, 0.30)
BAND_GAMMAS = (0.0, 0.2)
VARIANTS = ("v0", "v1")
NEUTRAL = "add-mul"
OUT = Path("research/c3r_g2/evidence_g2_qualification_20261028")


def _rng(*parts: object) -> random.Random:
    digest = hashlib.sha256(
        ":".join(str(p) for p in parts).encode()
    ).digest()
    return random.Random(digest)


@dataclass(frozen=True)
class Record:
    variant: str
    masked: bool
    plan: str
    success: bool


@dataclass(frozen=True)
class Task:
    variant: str


def other(plan: str) -> str:
    return "add-mul" if plan == "mul-add" else "mul-add"


def build_env(alpha: float, beta: float, gamma: float, seed: int):
    meta = _rng(SEED_DOMAIN, alpha, beta, gamma, seed, "meta")
    ctx_plan = "add-mul" if meta.randrange(2) == 0 else "mul-add"
    truth = {"v0": ctx_plan}
    truth["v1"] = other(ctx_plan) if beta > 0 else ctx_plan
    records: list[Record] = []
    rec_rng = _rng(SEED_DOMAIN, alpha, beta, gamma, seed, "records")
    for i in range(CORPUS):
        variant = VARIANTS[rec_rng.randrange(2)]
        masked = rec_rng.random() < gamma
        correct = truth[variant]
        truthful = rec_rng.random() < alpha
        records.append(
            Record(variant, masked, correct if truthful else other(correct), True)
        )
    tasks: list[Task] = []
    deviating = round(beta * TASKS)
    task_rng = _rng(SEED_DOMAIN, alpha, beta, gamma, seed, "tasks")
    variants = ["v1"] * deviating + ["v0"] * (TASKS - deviating)
    task_rng.shuffle(variants)
    tasks = [Task(v) for v in variants]
    return ctx_plan, truth, records, tasks


def majority(records: list[Record], floor: int, margin: int):
    wins = {"add-mul": 0, "mul-add": 0}
    for r in records:
        if r.success:
            wins[r.plan] += 1
    if sum(wins.values()) < floor or abs(wins["add-mul"] - wins["mul-add"]) < margin:
        return None
    return "add-mul" if wins["add-mul"] > wins["mul-add"] else "mul-add"


def compile_ctx(records: list[Record]) -> str:
    return majority(records, CTX_FLOOR, CTX_MARGIN) or NEUTRAL


def compile_var(records: list[Record]) -> dict[str, str]:
    ctx = compile_ctx(records)
    out = {}
    for variant in VARIANTS:
        pool = [r for r in records if r.variant == variant and not r.masked]
        plan = majority(pool, VAR_FLOOR, VAR_MARGIN)
        out[variant] = plan if plan is not None else ctx
    return out


def c_choice(records: list[Record], task: Task, member: int, task_index: int):
    pool = [
        r for r in records
        if not r.masked and r.variant == task.variant
    ]
    if len(pool) < 3:
        pool = pool + [r for r in records if not r.masked]
    rng = _rng(SEED_DOMAIN, "c", member, task_index, len(records))
    sample = rng.sample(pool, min(K_SAMPLE, len(pool))) if pool else []
    return majority(sample, 1, 1) or NEUTRAL


def run_env(alpha, beta, gamma, seed, d_ctx_override=None,
            d_var_oracle=False) -> dict[str, float]:
    ctx_plan, truth, records, tasks = build_env(alpha, beta, gamma, seed)
    d_ctx = d_ctx_override if d_ctx_override else compile_ctx(records)
    d_var = (
        {v: truth[v] for v in VARIANTS}
        if d_var_oracle else compile_var(records)
    )
    correct = {"C": 0, "D_CTX": 0, "D_VAR": 0}
    cells = MEMBERS * TASKS
    for m in range(MEMBERS):
        for t, task in enumerate(tasks):
            if c_choice(records, task, m, t) == truth[task.variant]:
                correct["C"] += 1
            if d_ctx == truth[task.variant]:
                correct["D_CTX"] += 1
            if d_var[task.variant] == truth[task.variant]:
                correct["D_VAR"] += 1
    return {k: v / cells for k, v in correct.items()}


def cell_report(alpha, beta, gamma) -> dict[str, object]:
    rows = [run_env(alpha, beta, gamma, s) for s in range(SEEDS_PER_CELL)]
    d_ctx = [r["D_CTX"] - r["C"] for r in rows]
    d_var = [r["D_VAR"] - r["C"] for r in rows]
    g = [r["D_VAR"] - r["D_CTX"] for r in rows]

    def classify(x: float) -> str:
        if x > TAU:
            return "positive"
        if x < -TAU:
            return "negative"
        return "tie"

    sign_sets = {
        "g": {classify(v) for v in g},
        "d_ctx": {classify(v) for v in d_ctx},
    }
    # a-priori rule prediction for G
    if beta == 0.0:
        rule = "G~0 (hypothesis; may be negative via support splitting)"
    elif alpha == 1.0 and gamma == 0.0:
        rule = "G>0 (rule-predicted)"
    else:
        rule = None  # evidence-determined
    return {
        "alpha": alpha, "beta": beta, "gamma": gamma,
        "mean_d_ctx": statistics.mean(d_ctx),
        "mean_d_var": statistics.mean(d_var),
        "mean_g": statistics.mean(g),
        "sd_g": statistics.stdev(g) if len(g) > 1 else 0.0,
        "g_signs_across_seeds": sorted(sign_sets["g"]),
        "d_ctx_signs_across_seeds": sorted(sign_sets["d_ctx"]),
        "a_priori_rule": rule,
        "seed_dependent_winner": len(sign_sets["g"]) > 1,
    }


def validity_probes() -> dict[str, object]:
    # V1: oracle-granularity swap must lift D_VAR to ceiling where
    # information exists; V2: corruption must collapse D_CTX.
    v1_g0 = [
        run_env(0.75, 0.30, 0.0, s, d_var_oracle=True)["D_VAR"]
        for s in range(SEEDS_PER_CELL)
    ]
    v1_g04 = [
        run_env(0.75, 0.30, 0.4, s, d_var_oracle=True)["D_VAR"]
        for s in range(SEEDS_PER_CELL)
    ]
    v2 = [
        run_env(0.75, 0.30, 0.0, s, d_ctx_override="zzz")["D_CTX"]
        for s in range(SEEDS_PER_CELL)
    ]
    return {
        "V1_oracle_granularity_mean_d_var_gamma0": statistics.mean(v1_g0),
        "V1_oracle_granularity_mean_d_var_gamma04": statistics.mean(v1_g04),
        "V1_valid": statistics.mean(v1_g0) == 1.0 and statistics.mean(v1_g04) == 1.0,
        "V2_corrupted_ctx_mean": statistics.mean(v2),
        "V2_valid": statistics.mean(v2) == 0.0,
    }


def main() -> int:
    cells = [
        cell_report(alpha, beta, gamma)
        for alpha in ALPHAS for beta in BETAS for gamma in GAMMAS
    ]
    probes = validity_probes()

    band = [
        c for c in cells
        if c["beta"] in BAND_BETAS and c["gamma"] in BAND_GAMMAS
    ]
    band_sds = [c["sd_g"] for c in band]
    sd_upper = max(band_sds) if band_sds else 0.0

    apparatus_valid = probes["V1_valid"] and probes["V2_valid"]
    # non-definitive generator: seed-dependent winners exist in the
    # pre-declared band (evidence, not rules, decides there)
    band_seed_dep = sum(1 for c in band if c["seed_dependent_winner"])
    generator_non_definitive = band_seed_dep >= 3

    g_positive_cells = sum(
        1 for c in cells if c["mean_g"] > TAU
    )
    g_nonpositive_cells = sum(
        1 for c in cells if c["mean_g"] <= TAU
    )
    d_ctx_positive_cells = sum(
        1 for c in cells if c["mean_d_ctx"] > TAU
    )

    report = {
        "schema": SCHEMA,
        "frozen_spec": {
            "grid": f"{len(ALPHAS)}x{len(BETAS)}x{len(GAMMAS)}"
                    f"={len(ALPHAS) * len(BETAS) * len(GAMMAS)} cells",
            "seeds_per_cell": SEEDS_PER_CELL,
            "corpus": CORPUS, "tasks": TASKS, "members": MEMBERS,
            "k_sample": K_SAMPLE, "tau": TAU,
            "analysis_band": "beta in {0.15,0.30} x gamma in {0.0,0.2}",
        },
        "validity_probes": probes,
        "apparatus_causal_valid": apparatus_valid,
        "generator_non_definitive": generator_non_definitive,
        "band_seed_dependent_cells": f"{band_seed_dep}/{len(band)}",
        "sign_map_summary": {
            "cells_with_G_positive": g_positive_cells,
            "cells_with_G_tie_or_negative": g_nonpositive_cells,
            "cells_with_D_CTX_beats_C": d_ctx_positive_cells,
        },
        "beta0_g_values": {
            f"alpha={a},gamma={g}": next(
                c["mean_g"] for c in cells
                if c["alpha"] == a and c["beta"] == 0.0 and c["gamma"] == g
            )
            for a in ALPHAS for g in GAMMAS
        },
        "band_g_sd_upper": sd_upper,
        "cells": cells,
        "verdict": (
            "CHECK PASSED: apparatus causally valid AND generator not "
            "outcome-determinative in the analysis band - proceed to "
            "confirmatory prereg preparation (no live launch)"
            if apparatus_valid and generator_non_definitive
            else "CHECK FAILED - this design CLOSES with zero sends"
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "no-forced-sign-report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(
        {k: v for k, v in report.items() if k != "cells"}, indent=2,
        sort_keys=True,
    ))
    print(f"report written: {out}", flush=True)
    return 0 if (apparatus_valid and generator_non_definitive) else 1


if __name__ == "__main__":
    raise SystemExit(main())
