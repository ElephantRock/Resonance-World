"""Fourth crossed G1 REAL-model exploratory pilot (internal-only, 40 sends max).

The default CLI is credential-free/offline. --live requires C3R_ZAI_API_KEY.
Eight balanced contexts, two development attempts/context, then 3-arm
qualification/context. Independent contexts run in parallel; no retries.
Results are descriptive evidence of prompt-reinserted feedback, not persistent
agent learning, powered G1 acceptance or verified vendor billing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from resonance_world.c3r_g1_crossed_local_evaluator import CrossedLocalEvaluator
from resonance_world.c3r_g1_crossed_plan import (
    CrossedPlan,
    PublicTask,
    evaluator_private_assignment,
    make_plan,
)
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import (
    MAX_GENERATION_TOKENS,
    PhysicalSendLedger,
    ZaiStandardModelPort,
)

MODEL = "glm-5.3"
SEND_MAXIMUM = 40
DEFAULT_TOKENS = 16384
_CHOICE_SHA = {s: hashlib.sha256(s.encode()).hexdigest() for s in ("A", "B")}


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


def prompt_for(task: PublicTask, *, source_history: tuple[dict[str, object], ...],
               arm: str) -> str:
    """No true rule or holdout feedback is present in any prompt."""
    if arm not in ("development", "learned", "fresh", "neutral"):
        raise ValueError("unknown G1 prompt arm")
    rule = (
        "A: (value + offset) * factor; B: value * factor + offset."
        if task.family == "arithmetic"
        else "A: replace lowercase 'ab' with 'z', then uppercase; "
        "B: uppercase, then replace lowercase 'ab' with 'z'."
    )
    history: list[str] = []
    if arm != "fresh":
        for row in source_history:
            if set(row) != {"task_id", "choice", "correct"}:
                raise ValueError("invalid source history fields")
            if not isinstance(row["task_id"], str):
                raise ValueError("source task identity invalid")
            if arm == "neutral":
                history.append(f'{row["task_id"]}: choice=?; success=?????')
            else:
                if row["choice"] not in ("A", "B") or type(row["correct"]) is not bool:
                    raise ValueError("learned history requires actual graded source")
                grade = "true " if row["correct"] else "false"
                history.append(
                    f'{row["task_id"]}: choice={row["choice"]}; success={grade}'
                )
    history_text = "\n".join(history) if history else "(none)"
    return (
        "Select the implementation used by this context. The context's "
        "hidden rule consistently selects either A or B; public operands "
        "do not reveal the hidden selection. Infer it only from graded "
        "development history, if supplied. If no actual graded outcomes "
        "are available (including masked or absent history), A is the "
        "pre-registered default guess: answer A immediately, without "
        "trying to infer hidden random assignments. If real graded "
        "outcomes are available, use them to select A or B. "
        "Reply exactly A or B.\n"
        f"Available implementations: {rule}\n"
        f"Public task: {json.dumps(task.record(), sort_keys=True)}\n"
        f"Past development evidence:\n{history_text}\n"
        "Reply exactly A or B."
    )


class DurableAttemptJournal:
    """Thread-safe, per-slot exclusive fsynced reservation before any send."""

    def __init__(self, root: Path, *, run_id: str) -> None:
        if (not root.is_absolute() or root.is_symlink()
                or root.stat().st_uid != os.geteuid()
                or root.stat().st_mode & 0o077):
            raise ValueError("pilot workspace must be owned/private")
        if not isinstance(run_id, str) or len(run_id) < 8 or len(run_id) > 64:
            raise ValueError("run ID length invalid")
        self.root = root / ("g1-live-" + hashlib.sha256(run_id.encode()).hexdigest())
        self.root.mkdir(mode=0o700, exist_ok=False)
        self.run_id = run_id
        self._guard = threading.Lock()
        self.reserved: set[int] = set()

    def reserve(self, *, index: int, prompt: str, model: str, route: str) -> None:
        if type(index) is not int or not 0 <= index < SEND_MAXIMUM:
            raise ValueError("unexpected physical send slot")
        record = {
            "schema": "g1-crossed-live-pre-send-v0.1",
            "run_id": self.run_id,
            "slot_index": index,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "model": model, "route": route,
            "state": "reserved_no_retry",
        }
        with self._guard:
            if index in self.reserved:
                raise ValueError("duplicate model attempt is forbidden")
            path = self.root / f"send-{index:02d}.json"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(json.dumps(record, sort_keys=True).encode() + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.reserved.add(index)
            directory_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

    @property
    def count(self) -> int:
        with self._guard:
            return len(self.reserved)


def _safe_send(
    slot_index: int, prompt: str, *,
    journal: DurableAttemptJournal,
    port_factory, model_id: str = MODEL,
) -> dict[str, object]:
    """One reserved physical attempt, never retried even on ambiguous timeout."""
    journal.reserve(index=slot_index, prompt=prompt, model=model_id, route="coding")
    port = port_factory()
    try:
        reply = port.complete_prompt(prompt)
    except Exception as exc:
        # Diagnostic metadata comes from locally controlled types/ledger only.
        # Neither exception messages nor raw provider bodies are persisted.
        attempts = getattr(getattr(port, "ledger", None), "records", [])
        latest = attempts[-1] if attempts else None
        safe_class = (
            latest.failure_class
            if latest is not None and latest.failure_class not in (None, "reserved")
            else type(exc).__name__
        )
        return {
            "status": "provider_error", "choice": None, "choice_sha256": None,
            "finish_reason": None, "completion_tokens": None,
            "reasoning_tokens": None, "prompt_tokens": None,
            "failure_class": safe_class
            if safe_class in (
                "HttpNon200", "ProviderTransportRejected", "TimeoutError",
                "URLError", "HTTPError", "JSONDecodeError", "OSError",
                "ValueError", "TypeError", "RuntimeError",
            ) else "OtherTransportError",
            "http_status": (
                latest.http_status if latest is not None
                and type(latest.http_status) is int else None
            ),
        }
    if not isinstance(reply, ModelChoiceCompletion) or reply.model_id != model_id:
        status = "invalid_format"
        choice = None
    elif reply.finish_reason != "stop" or reply.output not in ("A", "B"):
        status = "invalid_format"
        choice = None
    else:
        status = "accepted"
        choice = reply.output
    return {
        "status": status,
        "choice": choice,
        "choice_sha256": _CHOICE_SHA.get(reply.output)
        if isinstance(reply, ModelChoiceCompletion) else None,
        "finish_reason": reply.finish_reason if isinstance(reply, ModelChoiceCompletion) else None,
        "completion_tokens": reply.completion_tokens_reported
        if isinstance(reply, ModelChoiceCompletion) else None,
        "reasoning_tokens": reply.reasoning_tokens_reported
        if isinstance(reply, ModelChoiceCompletion) else None,
        "prompt_tokens": reply.prompt_tokens_reported
        if isinstance(reply, ModelChoiceCompletion) else None,
        "failure_class": None,
        "http_status": 200 if isinstance(reply, ModelChoiceCompletion) else None,
    }


def run_crossed_live(
    *, run_id: str, workspace: Path, port_factory,
    target_seed: bytes, max_workers: int = 4,
    enabled_families: tuple[str, ...] = ("arithmetic", "text"),
    model_id: str = MODEL, thinking_mode: str = "default",
    reasoning_effort: str = "low",
) -> dict[str, object]:
    """Two parallel phases; all source evidence closes before holdout sends."""
    if type(max_workers) is not int or not 1 <= max_workers <= 8:
        raise ValueError("live parallelism requires 1..8 workers")
    if (model_id not in ("glm-5.3", "glm-5.2", "glm-4.7")
            or thinking_mode != "default"
            or reasoning_effort not in ("low", "high", "max")):
        raise ValueError("model, thinking and reasoning effort must be supported")
    if (not isinstance(enabled_families, tuple) or not enabled_families
            or len(set(enabled_families)) != len(enabled_families)
            or not set(enabled_families) <= {"arithmetic", "text"}):
        raise ValueError("enabled families must be a nonempty supported subset")
    plan: CrossedPlan = make_plan()
    journal = DurableAttemptJournal(workspace, run_id=run_id)
    target = evaluator_private_assignment(plan, secret=target_seed)
    index_for = {
        (slot.unit_id, slot.task_id, slot.arm): i
        for i, slot in enumerate(plan.schedule)
    }
    def source_cell(cell):
        recorded = []
        observations = []
        for task in cell.development:
            index = index_for[(cell.unit_id, task.task_id, "learned")]
            if cell.family not in enabled_families:
                outcome = {
                    "status": "not_sent", "choice": None, "choice_sha256": None,
                    "finish_reason": None, "completion_tokens": None,
                    "reasoning_tokens": None, "prompt_tokens": None,
                    "failure_class": None, "http_status": None,
                }
            else:
                message = prompt_for(
                    task, source_history=tuple(recorded), arm="development"
                )
                outcome = _safe_send(
                    index, message, journal=journal, port_factory=port_factory,
                    model_id=model_id,
                )
            correct = (
                outcome["choice"] == target[cell.context_id]
                if outcome["status"] == "accepted" else None
            )
            if correct is not None:
                recorded.append({
                    "task_id": task.task_id,
                    "choice": outcome["choice"],
                    "correct": correct,
                })
            observations.append((index, outcome))
        return cell.unit_id, tuple(recorded), observations

    source_results: dict[int, dict[str, object]] = {}
    histories: dict[str, tuple[dict[str, object], ...]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(source_cell, cell) for cell in plan.cells]
        for future in as_completed(futures):
            unit, history, observations = future.result()
            histories[unit] = history
            for index, outcome in observations:
                source_results[index] = outcome

    # All sixteen source attempt receipts are frozen. Only contexts with two
    # accepted graded sources may perform holdout, rather than blocking all
    # otherwise healthy independent contexts on one provider failure.
    eligible_units = {
        unit for unit, history in histories.items() if len(history) == 2
    }
    evaluator_folder = journal.root / "source"
    evaluator_folder.mkdir(mode=0o700)
    evaluator = CrossedLocalEvaluator(
        run_id=run_id, private_target_seed=target_seed,
        signing_seed=os.urandom(32),
        internal_checkpoint_dir=evaluator_folder,
    )
    source_rows = []
    for index in range(16):
        response = source_results[index]
        signed = evaluator.submit(
            status=response["status"], choice=response["choice"],
        )
        source_rows.append(signed["signed_source_receipt"])
    freeze = evaluator.seal_source()
    if freeze["phase"] != "internal_source_frozen_qualification_allowed":
        raise ValueError("the sole internal source barrier did not close")

    cells_by_id = {cell.unit_id: cell for cell in plan.cells}
    def qualification_slot(index: int):
        slot = plan.schedule[index]
        cell = cells_by_id[slot.unit_id]
        task = cell.qualification[0]
        history = histories[slot.unit_id]
        if slot.unit_id not in eligible_units:
            return index, {
                "status": "not_sent", "choice": None, "choice_sha256": None,
                "finish_reason": None, "completion_tokens": None,
                "reasoning_tokens": None, "prompt_tokens": None,
                "failure_class": None, "http_status": None,
            }, None
        prompt = prompt_for(task, source_history=history, arm=slot.arm)
        return index, _safe_send(
            index, prompt, journal=journal, port_factory=port_factory,
            model_id=model_id,
        ), hashlib.sha256(prompt.encode()).hexdigest()

    qualification: dict[int, dict[str, object]] = {}
    prompt_hashes: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(qualification_slot, i) for i in range(16, 40)]
        for future in as_completed(futures):
            index, result, sha = future.result()
            qualification[index] = result
            prompt_hashes[index] = sha

    for index in range(16, 40):
        outcome = qualification[index]
        grade_hidden = evaluator.submit(
            status=outcome["status"], choice=outcome["choice"],
        )
        if (grade_hidden.get("phase") != "qualification_sealed"
                or set(grade_hidden) != {
                    "schema", "phase", "qualification_received",
                }):
            raise ValueError("holdout grade leaked into runtime")

    final = evaluator.finalize()
    if (final["actual_provider_sends"] != 0
            or final["scientific_acceptance"] is not False
            or len(final["receipts"]) != SEND_MAXIMUM):
        raise ValueError("terminal evaluator did not close frozen denominator")
    rows = []
    for index, slot in enumerate(plan.schedule):
        evidence = source_results[index] if index < 16 else qualification[index]
        grade = final["receipts"][index]["payload"]["correct"]
        rows.append({
            "index": index,
            "stage": slot.stage,
            "unit_id": slot.unit_id,
            "family": cells_by_id[slot.unit_id].family,
            "arm": slot.arm,
            "status": evidence["status"],
            "not_sent_reason": (
                "incomplete_source_for_context"
                if slot.stage == "qualification"
                and slot.unit_id not in eligible_units else None
            ),
            "choice_sha256": evidence["choice_sha256"],
            "correct": grade,
            "finish_reason": evidence["finish_reason"],
            "provider_failure_class": evidence["failure_class"],
            "provider_http_status": evidence["http_status"],
            "completion_tokens_reported": evidence["completion_tokens"],
            "reasoning_tokens_reported": evidence["reasoning_tokens"],
            "prompt_tokens_reported": evidence["prompt_tokens"],
            "qualification_prompt_sha256": prompt_hashes.get(index),
        })
    comparisons = {}
    for family in ("arithmetic", "text"):
        subset = [
            row for row in rows if row["stage"] == "qualification"
            and row["family"] == family
        ]
        comparisons[family] = {
            arm: {
                "correct": sum(row["correct"] is True for row in subset if row["arm"] == arm),
                "accepted": sum(row["status"] == "accepted" for row in subset if row["arm"] == arm),
                "prescribed": 4,
            }
            for arm in ("learned", "fresh", "neutral")
        }
    pairwise = {}
    for arm in ("learned", "fresh", "neutral"):
        chosen = [row for row in rows if row["stage"] == "qualification"
                  and row["arm"] == arm]
        pairwise[arm] = {
            "correct": sum(row["correct"] is True for row in chosen),
            "accepted": sum(row["status"] == "accepted" for row in chosen),
            "prescribed": 8,
        }
    return {
        "schema": "g1-crossed-fourth-live-observation-v0.1",
        "run_id": run_id, "model": model_id, "route": "coding",
        "thinking_mode": "enabled_requested",
        "reasoning_effort_requested": (
            reasoning_effort if model_id == "glm-5.3" else None
        ),
        "plan_digest": plan.public_digest,
        "source_lock_sha256": freeze["internal_source_lock_sha256"],
        "source_gate_closed": True,
        "source_contexts_eligible": len(eligible_units),
        "source_contexts_incomplete": len(plan.cells) - len(eligible_units),
        "enabled_families": list(enabled_families),
        "prescribed_attempts": SEND_MAXIMUM,
        "source_attempts": 16, "holdout_attempts": 24,
        "physical_sends_reserved": journal.count,
        "physical_sends_vendor_billed_attested": False,
        "records": rows,
        "by_family": comparisons, "qualification_by_arm": pairwise,
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "provider_prompt_token_parity_attested": False,
        "independent_model_session_memory_attested": False,
        "external_auditor_required": False,
        "scientific_acceptance": False,
        "control_fallback_policy": "default_A_if_no_actual_grades_v1",
        "interpretation": "exploratory_crossed_real_model_if_vendor_authenticated",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="40-attempt internal crossed GLM-5.3 pilot")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-id", default="g1-crossed-real-20261023-01")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_TOKENS)
    parser.add_argument("--model", choices=("glm-5.3", "glm-5.2", "glm-4.7"),
                        default=MODEL)
    parser.add_argument("--thinking-mode", choices=("default",), default="default")
    parser.add_argument("--reasoning-effort", choices=("low", "high", "max"),
                        default="low")
    parser.add_argument("--family", action="append", choices=("arithmetic", "text"))
    args = parser.parse_args(argv)
    plan = make_plan()
    if not args.live:
        print(json.dumps({
            "status": "offline_plan_only", "run_id": args.run_id,
            "public_plan_digest": plan.public_digest,
            "planned_model_sends": SEND_MAXIMUM,
            "physical_sends": 0, "scientific_acceptance": False,
        }, sort_keys=True))
        return 0
    if (args.workspace is None or not args.workspace.is_absolute()
            or not 1 <= args.max_tokens <= MAX_GENERATION_TOKENS
            or not 1 <= args.workers <= 8):
        raise SystemExit("invalid live experiment parameters")
    key = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("C3R_ZAI_API_KEY missing, no live sends")
    def port_factory():
        return ZaiStandardModelPort(
            api_key=key, model_id=args.model,
            ledger=PhysicalSendLedger(1), route="coding",
            enabled=True, timeout_seconds=180,
            max_tokens=args.max_tokens,
            thinking_mode=args.thinking_mode,
            reasoning_effort=args.reasoning_effort,
        )
    result = run_crossed_live(
        run_id=args.run_id, workspace=args.workspace,
        target_seed=os.urandom(32),
        port_factory=port_factory, max_workers=args.workers,
        enabled_families=tuple(args.family) if args.family else ("arithmetic", "text"),
        model_id=args.model, thinking_mode=args.thinking_mode,
        reasoning_effort=args.reasoning_effort,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if (result["source_gate_closed"] is True
                 and len(result["records"]) == SEND_MAXIMUM) else 2


if __name__ == "__main__":
    raise SystemExit(main())
