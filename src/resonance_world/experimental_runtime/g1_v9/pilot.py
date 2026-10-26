"""G1 v9 A/B live pilot: GLM-5.3 as the recorded decision port.

Owner authorization (2026-10-26): one single-universe pilot world, hard
cap of 420 physical provider sends, run on the pinned Z.AI endpoint with
the working campaign credential. This module is the operational
execution layer mandated by that decision; the frozen scientific
protocol (contract, evaluator, reducer registry, memory custody, replay
verification) is consumed unchanged.

Design invariants:

- every model decision enters the world through ``decide_via(port)`` and
  is recorded as an external-input event with ``model_id`` provenance;
  ``replay_branch`` re-executes the world from the recorded decisions
  and never calls the port - the scientific freeze guarantee;
- arm A keeps its full experience memory; arm B's memory is cleared
  exactly at the recorded ablation transaction; arm C answers from the
  sealed freeze-fork snapshot and never learns; arm D is the offline
  canonical baseline and never calls the provider;
- every decision consumes exactly one durable send slot BEFORE the HTTP
  call; failed sends (429/timeouts/malformed) are never replaced - the
  step's decision falls back to the arm's last valid ordering for that
  context (or ``AB``), the fallback is counted and disclosed;
- the hard cap auto-stops the run: a budget exception aborts with a
  partial report; no slot is ever replenished.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..kernel import WorldKernel
from ..replay import replay_branch
from ..store import KernelStore
from ..views import DecisionRequest, ModelDecisionPort
from .acceptance import _leak_scan, _memory_state_at_tick, _run_path
from .arms import CanonicalPolicy
from .contract import (
    ACQUISITION_BRANCH,
    ARM_A_BRANCH,
    ARM_B_BRANCH,
    ARM_C_BRANCH,
    ARM_D_BRANCH,
    G1V9Contract,
    default_contract,
)
from .evaluator import context_schedule, derive_evaluator_seed
from .memory import canonical_memory, latest_memory_state, record_memory_event
from .scenario import build_machine, present_context, seal_epoch, start_arm
from .send_ledger import PhysicalSendCapExceeded
from .zai_transport import SCIENCE_ANCHOR_DIGEST, DirectZaiQualificationTransport

PILOT_CAMPAIGN_ID = hashlib.sha256(
    f"{SCIENCE_ANCHOR_DIGEST}:zai:glm-5.3:pilot-ab-v1".encode()
).hexdigest()
PILOT_SEND_CAP = 420

_MODEL_ID = "glm-5.3-live-zai-v1"
_ORDERING_RE = re.compile(r"\b(AB|BA)\b")


class PilotBudgetExhausted(RuntimeError):
    """The 420-send pilot ledger is exhausted; the run stops."""


def _log_entry(context: str, ordering: str, outcome: bool | None) -> dict[str, Any]:
    return {"context": context, "ordering": ordering, "outcome": outcome}


class LiveGlmPolicy(ModelDecisionPort):
    """One live arm: GLM-5.3 decides, the arm semantics live in the prompt.

    - ``acquisition`` / ``adaptive`` (arm A): full experience memory.
    - ``memory-ablated`` (arm B): memory cleared at the ablation point;
      re-learns from its own post-ablation feedback only.
    - ``frozen`` (arm C): answers from the sealed freeze-fork snapshot;
      the memory never grows.
    """

    model_id = _MODEL_ID

    def __init__(
        self,
        arm_kind: str,
        *,
        branch: str,
        transport: DirectZaiQualificationTransport,
        sealed_memory: Mapping[str, Any] | None = None,
        pacing_seconds: float = 1.5,
        rng: random.Random | None = None,
    ) -> None:
        if arm_kind not in ("acquisition", "adaptive", "memory-ablated", "frozen"):
            raise ValueError(f"unknown live arm kind {arm_kind!r}")
        self.arm_kind = arm_kind
        self.branch = branch
        self.transport = transport
        self.pacing_seconds = pacing_seconds
        self._rng = rng or random.Random()
        self.calls = 0
        self.malformed = 0
        self.transport_errors = 0
        self.fallbacks = 0
        self._log: list[dict[str, Any]] = []
        self._last_seen: int | None = None
        self._context_tail: dict[str, list[bool]] = {}
        self._successes: dict[str, dict[str, int]] = {}
        self._attempts: dict[str, dict[str, int]] = {}
        self.chosen: list[tuple[str, str]] = []
        self.frozen_at: int | None = 0 if arm_kind == "frozen" else None
        if sealed_memory is not None:
            self.restore(sealed_memory)
            if arm_kind == "frozen":
                self.frozen_at = 0

    # -- memory custody (same shape as the frozen ContextMemoryPolicy) ----

    def snapshot(self) -> dict[str, Any]:
        return {
            "chosen": [list(item) for item in self.chosen],
            "outcomes": [entry["outcome"] for entry in self._log],
            "last_seen": self._last_seen,
            "successes": {c: dict(v) for c, v in self._successes.items()},
            "attempts": {c: dict(v) for c, v in self._attempts.items()},
            "context_tail": {c: list(v) for c, v in self._context_tail.items()},
            "frozen_at": self.frozen_at,
            "log": [dict(entry) for entry in self._log],
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        self.chosen = [tuple(item) for item in snapshot["chosen"]]
        self._last_seen = snapshot["last_seen"]
        self._successes = {c: dict(v) for c, v in snapshot["successes"].items()}
        self._attempts = {c: dict(v) for c, v in snapshot["attempts"].items()}
        self._context_tail = {c: list(v) for c, v in snapshot["context_tail"].items()}
        self.frozen_at = snapshot.get("frozen_at")
        log = snapshot.get("log")
        if log is None:
            outcomes = list(snapshot["outcomes"])
            log = [
                _log_entry(context, ordering, None)
                for context, ordering in self.chosen
            ]
            for index, entry in enumerate(log):
                if index < len(outcomes):
                    entry["outcome"] = outcomes[index]
        else:
            log = [dict(entry) for entry in log]
        self._log = log

    def ablate(self) -> None:
        self._log = []
        self._last_seen = None
        self._successes = {}
        self._attempts = {}
        self._context_tail = {}
        self.chosen = []

    # -- feedback channel ---------------------------------------------------

    def _absorb_feedback(self, total: int) -> None:
        if self._last_seen is None:
            self._last_seen = total
            return
        delta = total - self._last_seen
        self._last_seen = total
        if self.frozen_at is not None:
            return  # arm C: counters resync, memory never grows
        if delta not in (0, 1):
            raise ValueError("feedback channel inconsistent with the cadence")
        if self._log:
            entry = self._log[-1]
            if entry["outcome"] is None:
                outcome = delta == 1
                entry["outcome"] = outcome
                tail = self._context_tail.setdefault(entry["context"], [])
                tail.append(outcome)
                if outcome:
                    counts = self._successes.setdefault(
                        entry["context"], {"AB": 0, "BA": 0}
                    )
                    counts[entry["ordering"]] += 1

    # -- prompting -----------------------------------------------------------

    def _render_prompt(self, context: str) -> str:
        if self.arm_kind == "memory-ablated" and not self._log:
            experience = "(memory ablated - no experience available)"
        else:
            lines = []
            for entry in self._log:
                outcome = entry["outcome"]
                mark = "?" if outcome is None else ("ok" if outcome else "fail")
                lines.append(f"- {entry['context']}: {entry['ordering']} -> {mark}")
            experience = "\n".join(lines) if lines else "(none yet)"
        header = (
            "You are the decision module of an adaptive agent.\n"
            "World: there are 4 task contexts. In each context you choose one\n"
            "of two orderings: AB or BA. Exactly one ordering is rewarded per\n"
            "context, and the rewarded ordering can change without warning.\n"
            "After each of your decisions you learn whether it succeeded.\n"
            "Maximize successes.\n"
        )
        return (
            f"{header}\nYour experience, oldest first:\n{experience}\n\n"
            f"Current context: {context}\n\n"
            "Respond with exactly one word: AB or BA."
        )

    def _fallback_ordering(self, context: str) -> str:
        for entry in reversed(self._log):
            if entry["context"] == context and entry["outcome"] is not None:
                return entry["ordering"]
        for seen_context, ordering in reversed(self.chosen):
            if seen_context == context:
                return ordering
        return "AB"

    # -- the decision port ---------------------------------------------------

    def decide(self, request: DecisionRequest) -> dict[str, Any]:
        self.calls += 1
        context = str(request.observation.public_state["current_context"])
        total = int(request.observation.public_state.get("successes", 0))
        self._absorb_feedback(total)
        prompt = self._render_prompt(context)

        time.sleep(self.pacing_seconds + self._rng.random() * 0.8)
        try:
            result = self.transport.send(
                f"pilot:{self.branch}:{request.tick}", prompt
            )
        except PhysicalSendCapExceeded:
            raise PilotBudgetExhausted(
                "the 420-send pilot ledger is exhausted; run stopped"
            ) from None
        except Exception as error:  # consumed; never resent
            self.transport_errors += 1
            ordering = self._fallback_ordering(context)
            self.fallbacks += 1
            self._record_choice(context, ordering)
            print(
                f"[pilot] {self.branch}@{request.tick}: transport error "
                f"({type(error).__name__}) -> fallback {ordering}",
                flush=True,
            )
            return {
                "ordering": ordering,
                "context": context,
                "decided_at": request.tick,
            }

        answer = str(result.get("content", ""))
        match = _ORDERING_RE.search(answer.upper())
        if match is None:
            self.malformed += 1
            ordering = self._fallback_ordering(context)
            self.fallbacks += 1
            print(
                f"[pilot] {self.branch}@{request.tick}: malformed answer "
                f"({answer[:60]!r}) -> fallback {ordering}",
                flush=True,
            )
        else:
            ordering = match.group(1)
        self._record_choice(context, ordering)
        print(
            f"[pilot] {self.branch}@{request.tick}: {ordering} "
            f"(remaining={self.transport.remaining})",
            flush=True,
        )
        return {
            "ordering": ordering,
            "context": context,
            "decided_at": request.tick,
        }

    def _record_choice(self, context: str, ordering: str) -> None:
        self.chosen.append((context, ordering))
        attempts = self._attempts.setdefault(context, {"AB": 0, "BA": 0})
        attempts[ordering] += 1
        if self.frozen_at is None:
            self._log.append(_log_entry(context, ordering, None))


def pilot_transport(
    custody_dir: str | Path, credential_provider
) -> DirectZaiQualificationTransport:
    return DirectZaiQualificationTransport(
        ledger_base_dir=custody_dir,
        credential_provider=credential_provider,
        campaign_id=PILOT_CAMPAIGN_ID,
        send_cap=PILOT_SEND_CAP,
    )


@dataclass
class PilotReport:
    contract_digest: str
    pilot_campaign_id: str
    sends_consumed: int
    sends_remaining: int
    malformed_answers: int
    transport_errors: int
    fallback_decisions: int
    arms: dict[str, dict[str, Any]]
    ab_comparison: dict[str, Any]
    leak_scan_clean: bool
    all_replays_matched: bool
    world_valid_for_analysis: bool
    budget_exhausted_early: bool = False
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, sort_keys=True, default=str)


def _accuracy(successes: int, attempts: int) -> float:
    return successes / attempts if attempts else 0.0


def run_pilot(
    *,
    custody_dir: str | Path,
    credential_provider,
    contract: G1V9Contract | None = None,
    pacing_seconds: float = 1.5,
    seed_material: bytes | None = None,
    transport_factory=None,
) -> PilotReport:
    """Execute the single-universe live pilot (max 420 sends).

    ``transport_factory`` (zero-argument) lets tests inject an offline
    transport; production uses ``pilot_transport``.
    """

    contract = contract or default_contract()
    custody = Path(custody_dir)
    custody.mkdir(parents=True, exist_ok=True)

    commitment_path = custody / "pilot-commitment-key.bin"
    if commitment_path.exists():
        key = commitment_path.read_bytes()
    else:
        key = os.urandom(32)
        commitment_path.write_bytes(key)

    digest = contract.digest()
    seed = derive_evaluator_seed(
        seed_material
        if seed_material is not None
        else hashlib.sha256(f"{digest}:pilot-ab-v1".encode()).digest()
    )
    store = KernelStore(commitment_key=key)
    machine = build_machine(contract)
    contexts = context_schedule(
        seed,
        contract.acquisition_ticks + contract.measurement_ticks,
        contract.context_count,
        contract.decision_cadence,
    )
    transport = (
        transport_factory() if transport_factory is not None
        else pilot_transport(custody_dir, credential_provider)
    )

    def live(arm_kind: str, branch: str, sealed=None) -> LiveGlmPolicy:
        return LiveGlmPolicy(
            arm_kind,
            branch=branch,
            transport=transport,
            sealed_memory=sealed,
            pacing_seconds=pacing_seconds,
        )

    arm_a = arm_b = arm_c = arm_d = None
    policy_a = policy_b = policy_c = policy_d = None
    budget_exhausted_early = False
    try:
        # -- shared acquisition (ticks 0..499, 100 live decisions) ----------
        acquisition = start_arm(store, contract, ACQUISITION_BRANCH)
        learner = live("acquisition", ACQUISITION_BRANCH)
        table0 = seal_epoch(acquisition, epoch=0, seed=seed, contract=contract)

        arm_c: WorldKernel | None = None
        policy_c: LiveGlmPolicy | None = None
        for current in range(contract.acquisition_ticks):
            if current == contract.freeze_tick:
                record_memory_event(
                    kernel=acquisition,
                    tick=current,
                    kind="save",
                    memory=canonical_memory(learner.snapshot()),
                    memory_id=f"freeze-snapshot@{current}",
                )
                arm_c = acquisition.fork(ARM_C_BRANCH)
                policy_c = live(
                    "frozen",
                    ARM_C_BRANCH,
                    sealed=_memory_state_at_tick(
                        store, ACQUISITION_BRANCH, contract.freeze_tick
                    ),
                )
            decision_index = current // contract.decision_cadence
            context = (
                contexts[decision_index]
                if decision_index < len(contexts)
                else contexts[-1]
            )
            if current % contract.decision_cadence == 0:
                present_context(acquisition, context)
                acquisition.decide_via(learner)
            acquisition.schedule("world_pulse", {"tick": current})
            acquisition.advance()
            if acquisition.tick in contract.acquisition_checkpoints:
                acquisition.checkpoint(f"cp-{acquisition.tick}")

        # -- treatment save, balanced switch, paired fork --------------------
        record_memory_event(
            kernel=acquisition,
            tick=acquisition.tick,
            kind="save",
            memory=canonical_memory(learner.snapshot()),
            memory_id=f"treatment-snapshot@{acquisition.tick}",
        )
        seal_epoch(
            acquisition,
            epoch=1,
            seed=seed,
            contract=contract,
            previous_table=table0,
        )

        live_memory = latest_memory_state(store, ACQUISITION_BRANCH)
        arm_a = acquisition.fork(ARM_A_BRANCH)
        policy_a = live("adaptive", ARM_A_BRANCH, sealed=live_memory)
        arm_b = acquisition.fork(ARM_B_BRANCH)
        policy_b = live("memory-ablated", ARM_B_BRANCH, sealed=live_memory)
        policy_b.ablate()
        arm_b.emit(
            "memory_ablation",
            {"arm": ARM_B_BRANCH, "cleared": "agent_experience_memory"},
        )
        record_memory_event(
            kernel=arm_b,
            tick=arm_b.tick,
            kind="ablated",
            memory=canonical_memory(policy_b.snapshot()),
            memory_id=f"ablation@{arm_b.tick}",
        )

        # -- arm D: offline canonical baseline (zero provider sends) --------
        arm_d = start_arm(store, contract, ARM_D_BRANCH)
        seal_epoch(arm_d, epoch=0, seed=seed, contract=contract)
        policy_d = CanonicalPolicy()

        # -- measurement tails ------------------------------------------------
        _run_path(
            arm_a, policy_a, contexts=contexts, contract=contract,
            seal_switch=False, seed=seed, table0=table0, memory_custody=True,
        )
        _run_path(
            arm_b, policy_b, contexts=contexts, contract=contract,
            seal_switch=False, seed=seed, table0=table0, memory_custody=True,
        )
        _run_path(
            arm_c, policy_c, contexts=contexts, contract=contract,
            seal_switch=True, seed=seed, table0=table0,
        )
        _run_path(
            arm_d, policy_d, contexts=contexts, contract=contract,
            seal_switch=True, seed=seed, table0=table0,
        )
    except PilotBudgetExhausted:
        budget_exhausted_early = True
        print("[pilot] BUDGET EXHAUSTED - stopping with a partial report", flush=True)

    # -- report --------------------------------------------------------------
    kernels: dict[str, tuple[WorldKernel, Any]] = {}
    for name, kernel, policy in [
        ("A", arm_a, policy_a),
        ("B", arm_b, policy_b),
        ("C", arm_c, policy_c),
        ("D", arm_d, policy_d),
    ]:
        if kernel is not None:
            kernels[name] = (kernel, policy)

    arms_report: dict[str, dict[str, Any]] = {}
    for name, (kernel, policy) in kernels.items():
        public = kernel.state.public
        replay = replay_branch(store, BRANCH_BY_NAME[name], machine)
        arms_report[name] = {
            "branch": BRANCH_BY_NAME[name],
            "ticks": kernel.tick,
            "decisions": int(public["decisions"]),
            "own_decisions": policy.calls,
            "pre_accuracy": _accuracy(
                int(public["successes_pre"]), int(public["attempts_pre"])
            ),
            "post_accuracy": _accuracy(
                int(public["successes_post"]), int(public["attempts_post"])
            ),
            "adaptation_delta": round(
                _accuracy(int(public["successes_post"]), int(public["attempts_post"]))
                - _accuracy(int(public["successes_pre"]), int(public["attempts_pre"])),
                6,
            ),
            "replay_matched": kernel.state_hash() == replay.final_state_sha256,
            "port_calls": policy.calls,
            "malformed": getattr(policy, "malformed", 0),
            "transport_errors": getattr(policy, "transport_errors", 0),
            "fallbacks": getattr(policy, "fallbacks", 0),
        }

    a_post = arms_report.get("A", {}).get("post_accuracy", 0.0)
    b_post = arms_report.get("B", {}).get("post_accuracy", 0.0)
    ab = {
        "A_post": a_post,
        "B_post": b_post,
        "A_minus_B": round(a_post - b_post, 6),
        "C_post": arms_report.get("C", {}).get("post_accuracy", 0.0),
        "D_post": arms_report.get("D", {}).get("post_accuracy", 0.0),
    }

    leak_clean = all(_leak_scan(kernel) for kernel, _ in kernels.values())
    replays = bool(arms_report) and all(
        item["replay_matched"] for item in arms_report.values()
    )
    ledger_cap = transport._ledger.send_cap
    consumed = ledger_cap - transport._ledger.remaining()

    expected_own_decisions = {"A": 100, "B": 100, "C": 120, "D": 200}
    complete = all(
        arms_report.get(name, {}).get("own_decisions") == count
        for name, count in expected_own_decisions.items()
    )
    valid = bool(leak_clean and replays and complete)

    report = PilotReport(
        contract_digest=digest,
        pilot_campaign_id=PILOT_CAMPAIGN_ID,
        sends_consumed=consumed,
        sends_remaining=transport._ledger.remaining(),
        malformed_answers=sum(item.get("malformed", 0) for item in arms_report.values()),
        transport_errors=sum(
            item.get("transport_errors", 0) for item in arms_report.values()
        ),
        fallback_decisions=sum(
            item.get("fallbacks", 0) for item in arms_report.values()
        ),
        arms=arms_report,
        ab_comparison=ab,
        leak_scan_clean=leak_clean,
        all_replays_matched=replays,
        world_valid_for_analysis=bool(valid),
        budget_exhausted_early=budget_exhausted_early,
        notes=[]
        if complete
        else ["world incomplete: budget exhausted or transport stopped mid-run"],
    )
    (custody / "pilot-report.json").write_text(report.to_json(), encoding="utf-8")
    print("[pilot] report written to custody/pilot-report.json", flush=True)
    return report


BRANCH_BY_NAME = {
    "A": ARM_A_BRANCH,
    "B": ARM_B_BRANCH,
    "C": ARM_C_BRANCH,
    "D": ARM_D_BRANCH,
}
