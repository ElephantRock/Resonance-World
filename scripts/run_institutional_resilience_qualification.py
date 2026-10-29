"""Institutional Memory Resilience & Curation — deterministic offline qualification.

Owner GO (2026-10-29): ONE frozen attempt. 27 stress combinations
(staleness 0/0.15/0.35 x contradiction 0/10/25% x saturation 1x/4x/12x)
x 5 seeds = 135 deterministic organization chains; 5 generations each;
complete member replacement; fixed 6-record retrieval budget.

CAUSAL FAIRNESS (owner-mandated): CURATED and UNCURATED share the same
store schema, the SAME retrieval engine (6 most-recent eligible records
of the task's context), the same budget and admission opportunities.
The ONLY difference is the registered curation policy:
  C1 regime retirement (staleness) and C2 supersession (contradiction,
  >=3:1 support ratio) applied to the ELIGIBLE pool each generation.
Contradiction arises only from real noisy/stale observations
(wrong-plan successes); no evaluator forgery.

Arms: CURATED / UNCURATED / RESET (current-generation records only) /
FROZEN (pool frozen after generation 1). Members are idealized fresh
majority-of-retrieved deciders. Outcomes per generation; the chain
estimand is the CURATED-UNCURATED difference over stressed
generations 2-5. Pass conditions: curation WINS, HARMS and TIES all
occur across the grid without the generator forcing any, AND
evaluator validity (oracle->100%, corruption->0%) holds. Grid frozen;
one attempt; no re-tuning.
"""

from __future__ import annotations

import hashlib
import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "imrc-qualification-v0.1"
SEED_DOMAIN = "imrc-v1"
STALENESS = (0.0, 0.15, 0.35)
CONTRADICTION = (0.0, 0.10, 0.25)
SATURATION = (1, 4, 12)
SEEDS = 5
GENERATIONS = 5
CONTEXTS = ("c0", "c1")
TASKS_PER_GEN = 8
MEMBERS = 2
BUDGET = 6
TAU = 0.05
NEUTRAL = "add-mul"
PLANS = ("add-mul", "mul-add")
OUT = Path("research/c3r_g2/evidence_g2_qualification_20261028")


def _rng(*parts: object) -> random.Random:
    digest = hashlib.sha256(
        ":".join(str(p) for p in parts).encode()
    ).digest()
    return random.Random(digest)


def other(plan: str) -> str:
    return PLANS[0] if plan == PLANS[1] else PLANS[1]


@dataclass(frozen=True)
class Record:
    rid: str
    context: str
    plan: str
    success: bool
    generation: int


def admissions_per_generation(saturation: int) -> int:
    return max(1, round(saturation * BUDGET / GENERATIONS))


def run_chain(staleness: float, contradiction: float, saturation: int,
              seed: int, curated_override=None, member_oracle=False,
              member_corrupt=False) -> dict[str, object]:
    combo = (staleness, contradiction, saturation)
    n_new = admissions_per_generation(saturation)

    # per-context truth across generations (regime changes at transitions)
    truth: dict[str, list[str]] = {}
    for context in CONTEXTS:
        rng = _rng(SEED_DOMAIN, "truth", combo, seed, context)
        plans = [PLANS[rng.randrange(2)]]
        for _ in range(GENERATIONS - 1):
            if rng.random() < staleness:
                plans.append(other(plans[-1]))
            else:
                plans.append(plans[-1])
        truth[context] = plans

    store: list[Record] = []          # append-only admitted store
    eligible_full: list[Record] = []  # UNCURATED eligible pool
    eligible_cur: list[Record] = []   # CURATED eligible pool
    frozen_pool: list[Record] | None = None
    retired_total = 0
    policy_passes = 0
    per_gen: dict[str, list[float]] = {a: [] for a in
                                       ("CURATED", "UNCURATED", "RESET", "FROZEN")}

    def decide(pool: list[Record], context: str, generation: int,
               task_index: int, member: int) -> str:
        if member_oracle:
            return truth[context][generation]
        if member_corrupt:
            return other(truth[context][generation])
        ctx_pool = [r for r in pool if r.context == context]
        ctx_pool.sort(key=lambda r: (r.generation, r.rid), reverse=True)
        retrieved = ctx_pool[:BUDGET]
        if not retrieved:
            rng = _rng(SEED_DOMAIN, "neutral", combo, seed, generation,
                       task_index, member)
            return NEUTRAL if rng.randrange(2) == 0 else other(NEUTRAL)
        wins = {PLANS[0]: 0, PLANS[1]: 0}
        for r in retrieved:
            if r.success:
                wins[r.plan] += 1
        if wins[PLANS[0]] == wins[PLANS[1]]:
            return NEUTRAL
        return PLANS[0] if wins[PLANS[0]] > wins[PLANS[1]] else PLANS[1]

    for generation in range(GENERATIONS):
        # 1) admit this generation's records (real observations only)
        for context in CONTEXTS:
            rng = _rng(SEED_DOMAIN, "admit", combo, seed, context, generation)
            for i in range(n_new):
                truthful = rng.random() >= contradiction
                plan = truth[context][generation] if truthful else other(
                    truth[context][generation]
                )
                record = Record(
                    f"r-{combo}-{seed}-{context}-{generation}-{i}",
                    context, plan, True, generation,
                )
                store.append(record)

        # 2) refresh eligible pools (the fairness-critical divergence)
        eligible_full = list(store)
        if curated_override is None:
            pool = list(store)
            retired = 0
            policy_passes += 1
            # C1: regime retirement per context
            for context in CONTEXTS:
                ctx = [r for r in pool if r.context == context]
                current = [r for r in ctx if r.generation == generation]
                if current:
                    cur_majority = max(
                        PLANS,
                        key=lambda p: sum(
                            1 for r in current if r.success and r.plan == p
                        ),
                    )
                    older = [r for r in ctx if r.generation < generation]
                    if older:
                        old_majority = max(
                            PLANS,
                            key=lambda p: sum(
                                1 for r in older if r.success and r.plan == p
                            ),
                        )
                        if cur_majority != old_majority:
                            keep = [
                                r for r in pool
                                if not (
                                    r.context == context
                                    and r.generation < generation
                                    and r.success and r.plan == old_majority
                                )
                            ]
                            retired += len(pool) - len(keep)
                            pool = keep
            # C2: supersession within current regime (>= 3:1)
            for context in CONTEXTS:
                ctx = [r for r in pool if r.context == context and r.success]
                counts = {p: sum(1 for r in ctx if r.plan == p) for p in PLANS}
                lo, hi = sorted(PLANS, key=lambda p: counts[p])
                if counts[hi] >= 3 * counts[lo] and counts[lo] > 0:
                    keep = [
                        r for r in pool
                        if not (r.context == context and r.success
                                and r.plan == lo)
                    ]
                    retired += len(pool) - len(keep)
                    pool = keep
            eligible_cur = pool
            retired_total += retired
        else:
            eligible_cur = curated_override(store, generation)

        if generation == 0:
            frozen_pool = list(eligible_full)

        # 3) fresh members act (complete replacement, idealized deciders)
        rng_tasks = _rng(SEED_DOMAIN, "tasks", combo, seed, generation)
        outcomes = {a: [0, 0] for a in per_gen}
        for member in range(MEMBERS):
            for t in range(TASKS_PER_GEN):
                context = CONTEXTS[t % len(CONTEXTS)]
                correct_plan = truth[context][generation]
                for arm, pool in (
                    ("CURATED", eligible_cur),
                    ("UNCURATED", eligible_full),
                    ("RESET", [r for r in store if r.generation == generation]),
                    ("FROZEN", frozen_pool),
                ):
                    chosen = decide(pool, context, generation, t, member)
                    outcomes[arm][1] += 1
                    if chosen == correct_plan:
                        outcomes[arm][0] += 1
        for arm in per_gen:
            per_gen[arm].append(outcomes[arm][0] / outcomes[arm][1])

    stressed = range(1, GENERATIONS)  # generations 2..5 (0-indexed 1..4)
    delta = statistics.mean(
        c - u for c, u in zip(
            per_gen["CURATED"][1:], per_gen["UNCURATED"][1:]
        )
    )
    return {
        "staleness": staleness, "contradiction": contradiction,
        "saturation": saturation, "seed": seed,
        "per_generation": per_gen,
        "delta_resilience_gens2_5": delta,
        "curation_cost": {
            "retired_records": retired_total,
            "policy_passes": policy_passes,
        },
        "final_pool_sizes": {
            "uncurated": len(eligible_full), "curated": len(eligible_cur),
        },
    }


def classify(delta: float) -> str:
    if delta > TAU:
        return "curation_wins"
    if delta < -TAU:
        return "curation_harms"
    return "tie"


def main() -> int:
    chains = [
        run_chain(s, c, sat, seed)
        for s in STALENESS for c in CONTRADICTION for sat in SATURATION
        for seed in range(SEEDS)
    ]
    # evaluator validity probes at a representative combo
    oracle = run_chain(0.15, 0.10, 4, 0, member_oracle=True)
    corrupt = run_chain(0.15, 0.10, 4, 0, member_corrupt=True)
    oracle_all = all(
        v == 1.0 for gen in oracle["per_generation"].values() for v in gen
    )
    corrupt_all = all(
        v == 0.0 for gen in corrupt["per_generation"].values() for v in gen
    )

    combos: dict[tuple, list[float]] = {}
    for chain in chains:
        key = (chain["staleness"], chain["contradiction"], chain["saturation"])
        combos.setdefault(key, []).append(chain["delta_resilience_gens2_5"])
    combo_rows = []
    for key, deltas in sorted(combos.items()):
        mean = statistics.mean(deltas)
        combo_rows.append({
            "staleness": key[0], "contradiction": key[1],
            "saturation": key[2],
            "mean_delta": round(mean, 4),
            "sd": round(statistics.stdev(deltas), 4) if len(deltas) > 1 else 0.0,
            "classification": classify(mean),
        })
    classes = {r["classification"] for r in combo_rows}
    no_forced_sign = {"curation_wins", "curation_harms", "tie"} <= classes

    report = {
        "schema": SCHEMA,
        "grid": f"{len(STALENESS)}x{len(CONTRADICTION)}x{len(SATURATION)}"
                f"={len(STALENESS) * len(CONTRADICTION) * len(SATURATION)}",
        "chains": len(chains), "seeds": SEEDS,
        "generations": GENERATIONS, "retrieval_budget": BUDGET,
        "evaluator_validity": {
            "oracle_all_correct": oracle_all,
            "corruption_all_wrong": corrupt_all,
            "valid": oracle_all and corrupt_all,
        },
        "no_forced_sign": no_forced_sign,
        "class_counts": {
            name: sum(1 for r in combo_rows if r["classification"] == name)
            for name in ("curation_wins", "curation_harms", "tie")
        },
        "combo_rows": combo_rows,
        "chains_detail": chains,
        "verdict": (
            "QUALIFICATION PASSED: evaluator valid AND curation "
            "wins/harms/ties all occur without forced signs - proceed "
            "to owner review of the resilience map (no freeze, no sends)"
            if no_forced_sign and oracle_all and corrupt_all
            else "QUALIFICATION FAILED - design closes with zero sends"
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "imrc-qualification-report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(
        {k: v for k, v in report.items()
         if k not in ("chains_detail", "combo_rows")},
        indent=2, sort_keys=True,
    ))
    print(f"report written: {out}", flush=True)
    return 0 if (no_forced_sign and oracle_all and corrupt_all) else 1


if __name__ == "__main__":
    raise SystemExit(main())
