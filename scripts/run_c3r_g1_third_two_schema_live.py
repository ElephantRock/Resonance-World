"""Third exploratory REAL GLM-5.3 run: two task families and neutral-placebo arm.

Exactly 8 planned calls: 1 graded development per family + 1 holdout
triplet per family. Arithmetic target B; text target A. Each family has
a separate opaque context, so family and target are still confounded.
The placebo sees a grade-free development metadata placeholder padded
to the learned history's CHARACTER length, not audited token parity.
Not a preregistered, randomized, powered or independently graded G1 study.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Protocol

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import (
    Feedback,
    SchemaTask,
    apply_choice,
)
from resonance_world.c3r_g1_zai_transport import (
    MAX_GENERATION_TOKENS,
    PhysicalSendLedger,
    ZaiStandardModelPort,
)

MODEL = "glm-5.3"
MAX_SENDS = 8
TARGETS = {"arithmetic": "B", "text": "A"}
CONTEXTS = {
    "arithmetic": "c3r-v3-q4-arith-opaque",
    "text": "c3r-v3-r8-text-opaque",
}
SOURCE = {
    "arithmetic": SchemaTask(
        "dev-v3-arith-0", CONTEXTS["arithmetic"], "arithmetic",
        value=19, offset=4, factor=7,
    ),
    "text": SchemaTask(
        "dev-v3-text-0", CONTEXTS["text"], "text", text="abpraxab",
    ),
}
HOLDOUT = {
    "arithmetic": SchemaTask(
        "holdout-v3-arith-0", CONTEXTS["arithmetic"], "arithmetic",
        value=23, offset=6, factor=5,
    ),
    "text": SchemaTask(
        "holdout-v3-text-0", CONTEXTS["text"], "text", text="abconfluxab",
    ),
}
# Fixed interleaving. Not statistically randomized or order-balanced.
ORDER: tuple[tuple[str, str, str], ...] = (
    ("development", "arithmetic", "learned"),
    ("development", "text", "learned"),
    ("qualification", "text", "placebo"),
    ("qualification", "arithmetic", "fresh"),
    ("qualification", "text", "learned"),
    ("qualification", "arithmetic", "learned"),
    ("qualification", "text", "fresh"),
    ("qualification", "arithmetic", "placebo"),
)
CHOICE_DIGESTS = {
    c: hashlib.sha256(c.encode("utf-8")).hexdigest() for c in ("A", "B")
}


class Port(Protocol):
    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion: ...


@dataclass(frozen=True)
class TrialRow:
    stage: str
    family: str
    arm: str
    task_id: str
    status: str
    choice_sha256: str | None
    correct: bool | None
    finish_reason: str | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    prompt_tokens: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage, "family": self.family, "arm": self.arm,
            "task_id": self.task_id, "status": self.status,
            "choice_sha256": self.choice_sha256, "correct": self.correct,
            "finish_reason": self.finish_reason,
            "completion_tokens_reported": self.completion_tokens,
            "reasoning_tokens_reported": self.reasoning_tokens,
            "prompt_tokens_reported": self.prompt_tokens,
        }


def prompt_for(
    *, task: SchemaTask, arm: str,
    recorded: Feedback | None,
) -> str:
    """Learned sees actual grade; placebo gets grade-free padded metadata."""
    if recorded is None and arm == "learned":
        prior = "(none)"
    elif arm == "learned" and recorded is not None:
        prior = (
            f"{recorded.task_id}: choice={recorded.choice}; "
            f"success={str(recorded.success).lower()}"
        )
    elif arm == "fresh":
        prior = "(none)"
    elif arm == "placebo":
        if recorded is None:
            raise ValueError("placebo needs a completed development source")
        example = (
            f"{recorded.task_id}: choice={recorded.choice}; "
            f"success={str(recorded.success).lower()}"
        )
        neutral = f"{recorded.task_id}: choice=?; success=?"
        # Character padding minimizes crude length difference; does NOT
        # prove equal tokenization. No actual choice or grade is used.
        prior = neutral.ljust(len(example)) if len(neutral) <= len(example) else neutral
    else:
        raise ValueError("unknown arm")
    return task.prompt() + "\nPrior graded development attempts:\n" + prior


def experiment_lock() -> dict[str, object]:
    locked = {
        "schema": "g1-real-two-family-exploration-v0.1",
        "model": MODEL,
        "contexts": CONTEXTS,
        "targets": TARGETS,
        "development": {k: v.public_tuple() for k, v in SOURCE.items()},
        "holdouts": {k: v.public_tuple() for k, v in HOLDOUT.items()},
        "attempt_order": ORDER,
        "planned_provider_calls": MAX_SENDS,
        "reasoning_effort": "low",
        "technical_output_budget": 16384,
        "randomized": False,
        "token_parity_verified": False,
        "scientific_acceptance": False,
    }
    digest = hashlib.sha256(
        json.dumps(locked, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"sha256": digest, **locked}


def run_trial(port: Port, ledger: PhysicalSendLedger) -> dict[str, object]:
    feedback: dict[str, Feedback] = {}
    rows: list[TrialRow] = []
    stop = False
    for stage, family, arm in ORDER:
        task = SOURCE[family] if stage == "development" else HOLDOUT[family]
        status = "not_sent_after_failure" if stop else "pending"
        choice_hash = None
        correct = None
        finish = None
        completion_tokens = reasoning_tokens = prompt_tokens = None
        if not stop:
            history = feedback.get(family)
            prompt = prompt_for(task=task, arm=arm, recorded=history)
            try:
                response = port.complete_prompt(prompt)
            except Exception:
                status = "adapter_exception"
            else:
                if not isinstance(response, ModelChoiceCompletion):
                    status = "invalid_completion"
                elif response.model_id != MODEL:
                    status = "wrong_model"
                else:
                    finish = response.finish_reason
                    completion_tokens = response.completion_tokens_reported
                    reasoning_tokens = response.reasoning_tokens_reported
                    prompt_tokens = response.prompt_tokens_reported
                    choice_hash = hashlib.sha256(response.output.encode()).hexdigest()
                    if finish != "stop":
                        status = "unfinished_output"
                    elif response.output not in ("A", "B"):
                        status = "invalid_format"
                    else:
                        status = "accepted"
                        correct = apply_choice(task, response.output) == apply_choice(
                            task, TARGETS[family]
                        )
                        if stage == "development":
                            feedback[family] = Feedback(
                                task.task_id, task.context, response.output, correct,
                            )
            if status != "accepted":
                stop = True
        rows.append(TrialRow(
            stage, family, arm, task.task_id, status, choice_hash, correct,
            finish, completion_tokens, reasoning_tokens, prompt_tokens,
        ))

    qual = [row for row in rows if row.stage == "qualification"]
    by_family = {
        family: {
            arm: {
                "accepted": sum(
                    r.family == family and r.arm == arm and r.status == "accepted"
                    for r in qual
                ),
                "correct": sum(
                    r.family == family and r.arm == arm and r.correct is True
                    for r in qual
                ),
            } for arm in ("learned", "fresh", "placebo")
        } for family in ("arithmetic", "text")
    }
    return {
        "schema": "c3r-g1-third-live-multischema-neutral-control-v0.1",
        "lock": experiment_lock(),
        "prescribed_calls": MAX_SENDS,
        "development_accepted": sum(
            r.stage == "development" and r.status == "accepted" for r in rows
        ),
        "development_correct": sum(
            r.stage == "development" and r.correct is True for r in rows
        ),
        "qualifications": by_family,
        "complete_triplets": sum(
            all(by_family[fam][arm]["accepted"] == 1
                for arm in ("learned", "fresh", "placebo"))
            for fam in ("arithmetic", "text")
        ),
        "observations": [r.to_dict() for r in rows],
        "physical_ledger": ledger.to_dict(),
        "feedback_type": "actual_grades_vs_no_history_vs_grade_free_neutral_metadata",
        "matched_tokens_attested": False,
        "distinct_contexts": 2,
        "independent_learner_replication_attested": False,
        "independent_target_assignment_attested": False,
        "provider_billing_attested": False,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="8-call, two-family GLM-5.3 G1 exploration")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=16384)
    args = parser.parse_args(argv)
    if not 1 <= args.max_tokens <= MAX_GENERATION_TOKENS:
        raise SystemExit("unsupported generation budget")
    if not args.live:
        print(json.dumps({
            "status": "offline_no_provider_sends",
            "lock": experiment_lock(),
            "scientific_acceptance": False,
        }, sort_keys=True))
        return 0
    key = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("C3R_ZAI_API_KEY unavailable: no sends")
    ledger = PhysicalSendLedger(MAX_SENDS)
    port = ZaiStandardModelPort(
        api_key=key, model_id=MODEL, ledger=ledger,
        route="coding", enabled=True, timeout_seconds=180,
        max_tokens=args.max_tokens,
    )
    report = run_trial(port, ledger)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
