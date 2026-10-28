"""C3R-G2 causal qualification harness (offline, deterministic, no model).

Owner conditional GO (2026-10-28 evening): qualify the C/D comparison
CAUSALLY before any prereg freeze or live dispatch. This module proves,
with scripted members and fixture oracles only, that the four-arm
apparatus can MEASURE an organization-level difference rather than
build one - in particular that C (per-task raw-evidence interpretation)
and D (compile-once organizational procedure) are process-distinct
paths whose outcomes can genuinely diverge in both directions.

Scenario controls (each an independent fixture organization):
- S1 unambiguous corpus          -> C and D tie (honest-tie control)
- S2 noisy majority corpus       -> D > C (compilation wins measurably)
- S3 task-conditional truth      -> C > D (interpretation granularity wins)
- S4 insufficient support        -> compiler abstains, taxonomy path
- S5 corrupted procedure         -> D outcomes flip (mechanism liveness)
- S6 transport failure injection -> classified, denominator preserved

Every scenario reports per-arm outcomes, the failure taxonomy, and a
budget table (record reads, proposal slots, compile cost). All output
is canonical JSON and byte-identical across runs. Nothing here is
inferential evidence; nothing modifies historical artifacts; there are
no provider calls.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Literal

from .c3r_g2 import PLANS, Plan

Arm = Literal["A", "B", "C", "D", "D_MINUS"]
ARMS: tuple[Arm, ...] = ("A", "B", "C", "D", "D_MINUS")
MEMBERS = ("member-1", "member-2")
NEUTRAL_PLAN: Plan = PLANS[0]
SUPPORT_FLOOR = 8
MARGIN_FLOOR = 2
SAMPLE_K = 6  # per-task record budget for each raw-evidence member


@dataclass(frozen=True, slots=True)
class QTask:
    task_id: str
    context: str
    variant: str
    value: int
    offset: int
    factor: int


@dataclass(frozen=True, slots=True)
class Episode:
    episode_id: str
    context: str
    variant: str
    plan: Plan
    graded_success: bool


def _apply(task: QTask, plan: Plan) -> int:
    value = task.value
    for step in plan:
        value = value + task.offset if step == "add" else value * task.factor
    return value


class Oracle:
    """Evaluator only; truth may depend on (context, variant)."""

    def __init__(self, truth: dict[tuple[str, str], Plan]) -> None:
        self._truth = dict(truth)

    def grade(self, task: QTask, answer: int) -> bool:
        return answer == _apply(task, self._truth[(task.context, task.variant)])


def compile_procedure(
    episodes: list[Episode], context: str
) -> tuple[Plan | None, dict[str, int]]:
    """Compile-once mechanism: context-granular, support-floored, abstaining.

    Returns (plan_or_None, stats). None = ABSTENTION (insufficient
    support or tie); D members then use the pre-declared neutral default.
    """

    wins = {plan: 0 for plan in PLANS}
    total = 0
    for episode in episodes:
        if episode.context == context and episode.graded_success:
            wins[episode.plan] += 1
            total += 1
    stats = {"support": total, **{f"wins_{plan}": wins[plan] for plan in PLANS}}
    if total < SUPPORT_FLOOR:
        return None, stats
    a, b = PLANS
    if abs(wins[a] - wins[b]) < MARGIN_FLOOR:
        return None, stats
    return (a if wins[a] > wins[b] else b), stats


def member_reads(
    episodes: list[Episode], task: QTask, member: str, k: int = SAMPLE_K
) -> list[Episode]:
    """Bounded per-task interpretation sample (deterministic per member/task).

    Members of C see context AND variant tags on raw records and may
    condition on them - this is the extra interpretation opportunity C
    has over the compile-once contract, and it must not be crippled.
    """

    pool = [
        e for e in episodes
        if e.context == task.context and e.variant == task.variant
    ]
    if not pool:
        pool = [e for e in episodes if e.context == task.context]
    if not pool:
        pool = list(episodes)
    rng = random.Random(
        hashlib.sha256(f"read:{member}:{task.task_id}".encode()).digest()
    )
    return rng.sample(pool, min(k, len(pool)))


def raw_interpretation(sample: list[Episode]) -> Plan | None:
    wins = {plan: 0 for plan in PLANS}
    for episode in sample:
        if episode.graded_success:
            wins[episode.plan] += 1
    a, b = PLANS
    if wins[a] == wins[b]:
        return None  # member falls back to the neutral default
    return a if wins[a] > wins[b] else b


def independent_proposal(task: QTask, member: str) -> Plan:
    digest = hashlib.sha256(
        f"independent:{member}:{task.task_id}".encode()
    ).digest()
    return PLANS[digest[0] % 2]


@dataclass(slots=True)
class ScenarioSpec:
    name: str
    description: str
    episodes: list[Episode]
    tasks: list[QTask]
    truth: dict[tuple[str, str], Plan]
    transport_failures: set[tuple[str, str]] = field(default_factory=set)
    corrupt_plan: Plan | None = None  # S5: inject a flipped procedure


def _episode(
    eid: str, context: str, variant: str, plan: Plan, success: bool
) -> Episode:
    return Episode(eid, context, variant, plan, success)


def _task(tid: str, context: str, variant: str) -> QTask:
    digest = hashlib.sha256(f"task:{tid}".encode()).digest()
    return QTask(
        tid, context, variant,
        value=10 + digest[0] % 50,
        offset=1 + digest[1] % 5,
        factor=2 + digest[2] % 4,
    )


def scenario_s1_unambiguous() -> ScenarioSpec:
    context = "ctx-s1"
    episodes = [
        _episode(f"s1-e{i}", context, "v1", PLANS[1], True) for i in range(12)
    ] + [
        _episode(f"s1-f{i}", context, "v1", PLANS[0], False) for i in range(4)
    ]
    tasks = [_task(f"s1-t{i}", context, "v1") for i in range(24)]
    truth = {(context, "v1"): PLANS[1]}
    return ScenarioSpec(
        "S1_unambiguous_tie_control",
        "100%-consistent winners; C and D must tie by evidence clarity "
        "(NOT by algorithm identity)",
        episodes, tasks, truth,
    )


def scenario_s2_noisy_majority() -> ScenarioSpec:
    context = "ctx-s2"
    episodes = (
        [_episode(f"s2-w{i}", context, "v1", PLANS[1], True) for i in range(13)]
        + [_episode(f"s2-l{i}", context, "v1", PLANS[0], True) for i in range(7)]
    )
    tasks = [_task(f"s2-t{i}", context, "v1") for i in range(24)]
    truth = {(context, "v1"): PLANS[1]}
    return ScenarioSpec(
        "S2_noisy_majority_compilation_wins",
        "65/35 support; bounded per-member samples err on some tasks; "
        "full-corpus compilation is correct -> D must exceed C",
        episodes, tasks, truth,
    )


def scenario_s3_task_conditional() -> ScenarioSpec:
    context = "ctx-s3"
    episodes = (
        [_episode(f"s3-a{i}", context, "plain", PLANS[0], True) for i in range(12)]
        + [_episode(f"s3-b{i}", context, "plain", PLANS[1], True) for i in range(6)]
        + [_episode(f"s3-c{i}", context, "special", PLANS[1], True) for i in range(10)]
        + [_episode(f"s3-d{i}", context, "special", PLANS[0], True) for i in range(2)]
    )
    tasks = (
        [_task(f"s3-plain{i}", context, "plain") for i in range(12)]
        + [_task(f"s3-special{i}", context, "special") for i in range(12)]
    )
    truth = {(context, "plain"): PLANS[0], (context, "special"): PLANS[1]}
    return ScenarioSpec(
        "S3_task_conditional_interpretation_wins",
        "global per-context majority is wrong for the 'special' variant; "
        "the compiler's contract is context-granular while raw readers "
        "see variant tags -> C must exceed D",
        episodes, tasks, truth,
    )


def scenario_s4_abstention() -> ScenarioSpec:
    context = "ctx-s4"
    episodes = [
        _episode(f"s4-e{i}", context, "v1", PLANS[1], True) for i in range(5)
    ] + [
        _episode(f"s4-f{i}", context, "v1", PLANS[0], False) for i in range(3)
    ]
    tasks = [_task(f"s4-t{i}", context, "v1") for i in range(24)]
    truth = {(context, "v1"): PLANS[1]}
    return ScenarioSpec(
        "S4_insufficient_support_abstention",
        "support 5 < floor 8 -> compiler abstains; D falls back to the "
        "neutral default and the taxonomy must record the abstention",
        episodes, tasks, truth,
    )


def scenario_s5_corrupted_procedure() -> ScenarioSpec:
    spec = scenario_s1_unambiguous()
    spec.name = "S5_corrupted_procedure_liveness"
    spec.description = (
        "S1 corpus with a deliberately flipped injected procedure: D "
        "outcomes must flip vs S1 - the mechanism is live, not decorative"
    )
    spec.corrupt_plan = PLANS[0]
    return spec


def scenario_s6_transport_injection() -> ScenarioSpec:
    spec = scenario_s2_noisy_majority()
    spec.name = "S6_transport_failure_taxonomy"
    spec.description = (
        "S2 corpus with injected transport failures on specific "
        "member/task cells; classified as transport_error and preserved "
        "in the denominator"
    )
    spec.transport_failures = {("member-1", "s2-t0"), ("member-2", "s2-t7")}
    return spec


SCENARIOS = (
    scenario_s1_unambiguous,
    scenario_s2_noisy_majority,
    scenario_s3_task_conditional,
    scenario_s4_abstention,
    scenario_s5_corrupted_procedure,
    scenario_s6_transport_injection,
)


def run_scenario(spec: ScenarioSpec) -> dict[str, object]:
    oracle = Oracle(spec.truth)
    contexts = sorted({e.context for e in spec.episodes})
    compiled: dict[str, Plan | None] = {}
    compile_stats: dict[str, dict[str, int]] = {}
    for context in contexts:
        plan, stats = compile_procedure(spec.episodes, context)
        compiled[context] = plan
        compile_stats[context] = stats

    rows: dict[Arm, list[dict[str, object]]] = {arm: [] for arm in ARMS}
    budgets: dict[Arm, dict[str, int]] = {
        arm: {"record_reads": 0, "proposal_slots": 0, "compile_cost": 0}
        for arm in ARMS
    }
    for context in contexts:
        budgets["D"]["compile_cost"] += sum(
            1 for e in spec.episodes if e.context == context
        )
        budgets["D_MINUS"]["compile_cost"] = 0

    abstentions = 0
    for task in spec.tasks:
        truth_plan = spec.truth[(task.context, task.variant)]
        for member in MEMBERS:
            cell = (member, task.task_id)
            # Arm A: independent, no evidence
            plan_a = independent_proposal(task, member)
            # Arm C: per-task bounded raw interpretation
            sample = member_reads(spec.episodes, task, member)
            budgets["C"]["record_reads"] += len(sample)
            plan_c = raw_interpretation(sample)
            c_fallback = plan_c is None
            if c_fallback:
                plan_c = NEUTRAL_PLAN
            # Arm D: compiled procedure or neutral fallback on abstention
            d_fallback = compiled[task.context] is None
            if d_fallback:
                abstentions += 1
            plan_d_effective = compiled[task.context] or NEUTRAL_PLAN
            if spec.corrupt_plan is not None:
                plan_d_effective = spec.corrupt_plan
            # Arm B / D_MINUS: fixed neutral procedure, no evidence
            for arm in ARMS:
                budgets[arm]["proposal_slots"] += 1
                if (member, task.task_id) in spec.transport_failures and arm in ("C", "D"):
                    rows[arm].append({
                        "task_id": task.task_id, "member": member,
                        "plan": None, "classification": "transport_error",
                        "correct": False,
                    })
                    continue
                plan = {
                    "A": plan_a,
                    "B": NEUTRAL_PLAN,
                    "C": plan_c,
                    "D": plan_d_effective,
                    "D_MINUS": NEUTRAL_PLAN,
                }[arm]
                classification = "correct" if plan == truth_plan else "wrong"
                extra = None
                if arm == "C" and c_fallback:
                    extra = "interpretation_tie_fallback"
                if arm == "D" and d_fallback:
                    extra = "abstention_fallback"
                rows[arm].append({
                    "task_id": task.task_id, "member": member,
                    "plan": plan, "classification": classification,
                    "correct": oracle.grade(task, _apply(task, plan)),
                    "subpath": extra,
                })

    def summary(arm: Arm) -> dict[str, object]:
        arm_rows = rows[arm]
        return {
            "attempts": len(arm_rows),
            "correct": sum(1 for r in arm_rows if r["classification"] == "correct"),
            "wrong": sum(1 for r in arm_rows if r["classification"] == "wrong"),
            "transport_error": sum(
                1 for r in arm_rows if r["classification"] == "transport_error"
            ),
            "fallbacks": sum(1 for r in arm_rows if r.get("subpath")),
            "budget": budgets[arm],
        }

    paired = {
        "d_minus_c_correct": sum(
            1 for rd, rc in zip(rows["D"], rows["C"])
            if rd["classification"] == "correct"
            and rc["classification"] != "correct"
        ) - sum(
            1 for rd, rc in zip(rows["D"], rows["C"])
            if rc["classification"] == "correct"
            and rd["classification"] != "correct"
        ),
        "d_minus_b_correct": sum(
            1 for rd, rb in zip(rows["D"], rows["B"])
            if rd["classification"] == "correct"
            and rb["classification"] != "correct"
        ) - sum(
            1 for rd, rb in zip(rows["D"], rows["B"])
            if rb["classification"] == "correct"
            and rd["classification"] != "correct"
        ),
    }
    return {
        "scenario": spec.name,
        "description": spec.description,
        "noninferential": True,
        "compiled": {c: compiled[c] for c in contexts},
        "compile_stats": compile_stats,
        "abstention_fallback_cells": abstentions,
        "arms": {arm: summary(arm) for arm in ARMS},
        "paired_counts": paired,
        "budget_parity": {
            "c_total_record_reads": budgets["C"]["record_reads"],
            "d_compile_reads": budgets["D"]["compile_cost"],
            "c_reads_minus_d_compile": (
                budgets["C"]["record_reads"] - budgets["D"]["compile_cost"]
            ),
            "proposal_slots_equal": len(
                {budgets[arm]["proposal_slots"] for arm in ARMS}
            ) == 1,
        },
    }


def build_report() -> dict[str, object]:
    return {
        "schema": "c3r-g2-causal-qualification-v0.1",
        "noninferential": True,
        "no_provider_calls": True,
        "scenarios": [run_scenario(factory()) for factory in SCENARIOS],
    }


def main() -> int:
    print(json.dumps(build_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
