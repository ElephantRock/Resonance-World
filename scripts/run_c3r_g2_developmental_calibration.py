"""G2 developmental variance-calibration stage (frozen, 384-send cap).

Protocol: research/c3r_g2/G2_DEVELOPMENTAL_CALIBRATION_PROTOCOL_20261028.md
Owner GO (2026-10-28 night): ONE non-inferential stage estimating the
organization-level variance of the paired D-C difference, the response
validity rate and the real cost. 12 organizations (4 per environment
class), arms C and D only, 8 tasks x 2 fresh members per organization,
isolated session per arm. NO confirmatory freeze, NO full campaign.

Slot plan: org o block = o*32..o*32+31; C = first 16 (m*8+t), D = 16+.
Prompts reuse the request-class probe's exact shapes. Abstention is an
operational flag independent of grading. Developmental fixtures are
seed-locked and excluded from any confirmatory sample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from pathlib import Path

from resonance_world.c3r_g2 import PLANS
from resonance_world.c3r_g2_causal_qualification import (
    NEUTRAL_PLAN,
    QTask,
    compile_procedure,
    member_reads,
)
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort
from run_c3r_g2_request_class_probe import (
    _dispatch,
    c_class_prompt,
    d_class_prompt,
)

SCHEMA = "c3r-g2-developmental-calibration-v0.1"
MODEL = "glm-5.3"
ORG_COUNT = 12
TASKS_PER_ORG = 8
MEMBERS_PER_ORG = 2
ARMS = ("C", "D")
CAMPAIGN_SLOTS = 384
SAMPLE_K = 6
SEED_DOMAIN = "g2-devcal-v1"
CLASSES = (
    "unambiguous",
    "noisy_majority",
    "task_conditional",
)


class DevCalLedger:
    """Permanent per-workspace O_EXCL ledger enforcing the 384-send cap."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def reserve(self, index: int, session: str) -> None:
        with self._lock:
            path = self.root / f"devcal-slot-{index:03d}.json"
            if path.exists():
                raise RuntimeError(f"slot {index} already reserved: double dispatch")
            if index >= CAMPAIGN_SLOTS:
                raise RuntimeError(f"slot {index} exceeds the 384-send cap")
            payload = json.dumps({
                "run_id": self.run_id, "session": session, "index": index,
                "reserved_no_retry": True,
            }, sort_keys=True).encode() + b"\n"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())

    @property
    def consumed(self) -> int:
        return sum(1 for _ in self.root.glob("devcal-slot-*.json"))


def org_class(org_index: int) -> str:
    return CLASSES[org_index // 4]


def _rng(*parts: object) -> random.Random:
    digest = hashlib.sha256(
        ":".join(str(p) for p in parts).encode()
    ).digest()
    return random.Random(digest)


def _truth_plan(rng: random.Random) -> str:
    return PLANS[rng.randrange(2)]


def build_org(org_index: int) -> dict[str, object]:
    """Deterministic organization fixture: corpus, truth, tasks, compile."""

    cls = org_class(org_index)
    seed = f"{SEED_DOMAIN}:org:{org_index}"
    rng = _rng(seed, "meta")
    true_plan = _truth_plan(rng)
    other = PLANS[0] if true_plan == PLANS[1] else PLANS[1]
    corpus: list[dict[str, object]] = []
    truth: dict[tuple[str, str], str] = {}
    tasks: list[QTask] = []

    def add_episode(eid: str, variant: str, plan: str, success: bool) -> None:
        corpus.append({
            "episode_id": f"org{org_index}-{eid}", "context": "ctx",
            "variant": variant, "plan": plan, "graded_success": success,
        })

    def add_task(tid: str, variant: str) -> None:
        trng = _rng(seed, "task", tid)
        tasks.append(QTask(
            task_id=f"org{org_index}-{tid}", context="ctx", variant=variant,
            value=10 + trng.randrange(50),
            offset=1 + trng.randrange(5),
            factor=2 + trng.randrange(4),
        ))

    if cls == "unambiguous":
        for i in range(16):
            add_episode(f"e{i}", "v1", true_plan, True)
        for i in range(4):
            add_episode(f"f{i}", "v1", other, False)
        truth[("ctx", "v1")] = true_plan
        for t in range(TASKS_PER_ORG):
            add_task(f"t{t}", "v1")
    elif cls == "noisy_majority":
        for i in range(13):
            add_episode(f"e{i}", "v1", true_plan, True)
        for i in range(7):
            add_episode(f"f{i}", "v1", other, True)
        truth[("ctx", "v1")] = true_plan
        for t in range(TASKS_PER_ORG):
            add_task(f"t{t}", "v1")
    else:  # task_conditional
        for i in range(12):
            add_episode(f"e{i}", "plain", true_plan, True)
        for i in range(6):
            add_episode(f"f{i}", "plain", other, True)
        for i in range(10):
            add_episode(f"g{i}", "special", other, True)
        for i in range(2):
            add_episode(f"h{i}", "special", true_plan, True)
        truth[("ctx", "plain")] = true_plan
        truth[("ctx", "special")] = other
        for t in range(4):
            add_task(f"t{t}", "plain")
        for t in range(4, TASKS_PER_ORG):
            add_task(f"t{t}", "special")

    procedure, compile_stats = compile_procedure(
        [_episode_from(c) for c in corpus], "ctx"
    )
    return {
        "org_index": org_index, "class": cls,
        "corpus": corpus, "truth": truth, "tasks": tasks,
        "procedure": procedure, "compile_stats": compile_stats,
    }


def _episode_from(record: dict[str, object]):
    from resonance_world.c3r_g2_causal_qualification import Episode

    return Episode(
        str(record["episode_id"]), str(record["context"]),
        str(record["variant"]), record["plan"], bool(record["graded_success"]),
    )


def all_orgs() -> list[dict[str, object]]:
    return [build_org(i) for i in range(ORG_COUNT)]


def cell_slot(org_index: int, arm: str, member: int, task: int) -> int:
    return org_index * 32 + (0 if arm == "C" else 16) + member * 8 + task


def _expected_answer(truth: dict[tuple[str, str], str], task: QTask) -> int:
    from resonance_world.c3r_g2_causal_qualification import _apply

    return _apply(task, truth[(task.context, task.variant)])


def _c_fixture(org: dict[str, object], member: int, task: QTask):
    sample = member_reads(
        [_episode_from(c) for c in org["corpus"]],
        task, f"org{org['org_index']}-member{member}", k=SAMPLE_K,
    )
    return {"sample": sample, "task": task, "procedure": None}


def _d_fixture(org: dict[str, object], task: QTask):
    # on abstention the members execute the pre-declared neutral procedure
    procedure = org["procedure"] if org["procedure"] is not None else NEUTRAL_PLAN
    return {"sample": [], "task": task, "procedure": procedure}


def run_org(
    workspace: Path, run_id: str, org_index: int, api_key: str
) -> dict[str, object]:
    """One organization: 32 sends (2 arms x 2 members x 8 tasks)."""

    manifest = json.loads(
        (workspace / "devcal-manifest.json").read_text(encoding="utf-8")
    )
    org = manifest["organizations"][org_index]
    truth = {
        (t["context"], t["variant"]): t["plan"] for t in org["truth"]
    }
    ledger = DevCalLedger(workspace / "devcal-ledger", run_id)
    rows: list[dict[str, object]] = []

    for arm in ARMS:
        for member in range(MEMBERS_PER_ORG):
            for task_index, task_record in enumerate(org["tasks"]):
                task = QTask(
                    task_record["task_id"], task_record["context"],
                    task_record["variant"], task_record["value"],
                    task_record["offset"], task_record["factor"],
                )
                slot = cell_slot(org_index, arm, member, task_index)
                if arm == "C":
                    fixture = _c_fixture(org, member, task)
                else:
                    fixture = _d_fixture(org, task)
                prompt = c_class_prompt(fixture) if arm == "C" else d_class_prompt(fixture)
                expected = _expected_answer(truth, task)
                abstain = arm == "D" and org["procedure"] is None
                ledger.reserve(slot, f"org{org_index}-{arm}-m{member}-t{task_index}")
                started = time.monotonic()
                try:
                    completion = _dispatch(api_key, prompt)
                    answer = completion.output.strip()
                    finish = completion.finish_reason
                    row = {
                        "arm": arm, "member": member,
                        "task_id": task.task_id, "slot": slot,
                        "latency_ms": round((time.monotonic() - started) * 1000, 1),
                        "finish_reason": finish, "answer": answer,
                        "prompt_tokens": completion.prompt_tokens_reported,
                        "completion_tokens": completion.completion_tokens_reported,
                        "abstention_fallback": abstain,
                    }
                    if finish == "stop" and answer:
                        row["classification"] = "completed_parseable"
                        row["correct"] = (
                            answer.isdigit() and int(answer) == expected
                        )
                    elif finish == "length":
                        row["classification"] = "length"
                        row["correct"] = False
                    else:
                        row["classification"] = "empty"
                        row["correct"] = False
                except Exception as exc:
                    row = {
                        "arm": arm, "member": member, "task_id": task.task_id,
                        "slot": slot,
                        "latency_ms": round((time.monotonic() - started) * 1000, 1),
                        "classification": "transport_error",
                        "failure_class": type(exc).__name__[:40],
                        "answer": None, "correct": False,
                        "prompt_tokens": None, "completion_tokens": None,
                        "abstention_fallback": abstain,
                    }
                rows.append(row)

    summary = {
        "schema": SCHEMA,
        "org_index": org_index,
        "class": org["class"],
        "sends": len(rows),
        "rows": rows,
        "per_arm": {
            arm: {
                "cells": sum(1 for r in rows if r["arm"] == arm),
                "correct": sum(
                    1 for r in rows if r["arm"] == arm and r["correct"]
                ),
                "parseable": sum(
                    1 for r in rows
                    if r["arm"] == arm and r["classification"] == "completed_parseable"
                ),
                "abstention_flags": sum(
                    1 for r in rows
                    if r["arm"] == arm and r["abstention_fallback"]
                ),
                "completion_tokens": sum(
                    r["completion_tokens"] or 0
                    for r in rows if r["arm"] == arm
                ),
                "latency_ms_total": sum(
                    r["latency_ms"] for r in rows if r["arm"] == arm
                ),
            }
            for arm in ARMS
        },
    }
    out = workspace / f"devcal-org-{org_index:02d}.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"[devcal] org {org_index} ({org['class']}): "
          f"C {summary['per_arm']['C']['correct']}/16, "
          f"D {summary['per_arm']['D']['correct']}/16, sends {len(rows)}",
          flush=True)
    return summary


def run_manifest(workspace: Path, run_id: str) -> dict[str, object]:
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "protocol": "G2_DEVELOPMENTAL_CALIBRATION_PROTOCOL_20261028",
        "organizations": [
            {
                "org_index": o["org_index"], "class": o["class"],
                "corpus": o["corpus"], "truth": [
                    {"context": ctx, "variant": var, "plan": plan}
                    for (ctx, var), plan in o["truth"].items()
                ],
                "tasks": [
                    {
                        "task_id": t.task_id, "context": t.context,
                        "variant": t.variant, "value": t.value,
                        "offset": t.offset, "factor": t.factor,
                    }
                    for t in o["tasks"]
                ],
                "procedure": o["procedure"],
                "compile_stats": o["compile_stats"],
            }
            for o in all_orgs()
        ],
        "campaign_slots": CAMPAIGN_SLOTS,
        "scientific_acceptance": False,
        "noninferential": True,
    }
    path = workspace / "devcal-manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing_canonical = json.dumps(
            existing["organizations"], sort_keys=True
        )
        fresh_canonical = json.dumps(
            manifest["organizations"], sort_keys=True
        )
        if existing_canonical != fresh_canonical:
            raise ValueError("manifest drift: frozen fixtures changed")
        print("manifest already frozen and identical", flush=True)
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"manifest frozen: {path}", flush=True)
    return manifest


def run_report(workspace: Path) -> dict[str, object]:
    """Aggregate org-level variance, validity, cost (non-inferential)."""

    import math
    import statistics

    required = [f"devcal-org-{i:02d}.json" for i in range(ORG_COUNT)]
    missing = [n for n in required if not (workspace / n).exists()]
    if missing:
        raise FileNotFoundError(f"calibration incomplete, missing: {missing}")

    orgs = [
        json.loads((workspace / n).read_text(encoding="utf-8"))
        for n in required
    ]
    per_org_diffs: list[float] = []
    by_class: dict[str, list[float]] = {c: [] for c in CLASSES}
    validity = {"C": [0, 0], "D": [0, 0]}  # parseable / total
    tokens = {"C": 0, "D": 0}
    latency = {"C": 0.0, "D": 0.0}
    abstain_flags = 0
    sends_total = 0
    for org in orgs:
        c = org["per_arm"]["C"]
        d = org["per_arm"]["D"]
        diff = (d["correct"] - c["correct"]) / 16.0
        per_org_diffs.append(diff)
        by_class[org["class"]].append(diff)
        for arm in ARMS:
            pa = org["per_arm"][arm]
            validity[arm][0] += pa["parseable"]
            validity[arm][1] += pa["cells"]
            tokens[arm] += pa["completion_tokens"]
            latency[arm] += pa["latency_ms_total"]
        abstain_flags += org["per_arm"]["D"]["abstention_flags"]
        sends_total += org["sends"]

    pooled_sd = statistics.stdev(per_org_diffs) if len(per_org_diffs) > 1 else 0.0
    pooled_mean = statistics.mean(per_org_diffs)
    # conservative chi-square upper bound on the org-level SD (df=11)
    chi2_upper = 4.57  # 0.05 upper quantile approx for df=11 (5.58 lower not needed)
    sd_upper_bound = pooled_sd * math.sqrt(11 / chi2_upper) if pooled_sd else 0.0

    def required_n(sd: float, delta: float = 0.05, alpha: float = 0.05,
                   power: float = 0.8) -> int:
        z_alpha, z_beta = 1.645, 0.842
        return math.ceil((z_alpha + z_beta) ** 2 * sd * sd / (delta * delta))

    report = {
        "schema": SCHEMA,
        "noninferential": True,
        "campaign": "g2-developmental-calibration-20261028",
        "sends_total": sends_total,
        "send_cap": CAMPAIGN_SLOTS,
        "org_mean_paired_diffs": [
            {"org": o["org_index"], "class": o["class"],
             "diff": per_org_diffs[i]}
            for i, o in enumerate(orgs)
        ],
        "pooled": {
            "mean_diff": pooled_mean,
            "sd_point": pooled_sd,
            "sd_upper_bound_chi2_df11": sd_upper_bound,
        },
        "by_class": {
            c: {
                "mean": statistics.mean(v) if v else None,
                "sd": statistics.stdev(v) if len(v) > 1 else None,
                "n_orgs": len(v),
            }
            for c, v in by_class.items()
        },
        "validity": {
            arm: {
                "parseable": validity[arm][0], "cells": validity[arm][1],
                "rate": validity[arm][0] / validity[arm][1]
                if validity[arm][1] else None,
            }
            for arm in ARMS
        },
        "abstention_flag_cells_D": abstain_flags,
        "cost": {
            "completion_tokens": tokens,
            "completion_token_ceiling": CAMPAIGN_SLOTS * 4096,
            "latency_ms_totals": latency,
        },
        "conservative_n_inputs": {
            "note": "inputs for the freeze decision only; joint-gate "
                    "power simulation happens at freeze",
            "n_at_sd_point": required_n(pooled_sd),
            "n_at_sd_upper_bound": required_n(sd_upper_bound),
        },
        "scientific_acceptance": False,
    }
    path = workspace / "devcal-report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="G2 developmental variance calibration (384-send cap)"
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("manifest", "run", "report"))
    parser.add_argument("--org", type=int)
    parser.add_argument("--api-key", default=os.environ.get("C3R_ZAI_API_KEY", ""))
    args = parser.parse_args()
    workspace = args.workspace
    workspace.mkdir(parents=True, exist_ok=True)
    if args.session == "manifest":
        run_manifest(workspace, args.run_id)
        return 0
    if args.session == "report":
        run_report(workspace)
        return 0
    if not args.api_key:
        parser.error("C3R_ZAI_API_KEY (or --api-key) is required")
    if args.org is None or not 0 <= args.org < ORG_COUNT:
        parser.error("run sessions require --org (0..11)")
    run_org(workspace, args.run_id, args.org, args.api_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
