"""Offline dress rehearsal for the live G1 v9 A/B pilot.

Runs the FULL single-universe pilot flow with a scripted transport
(zero network) on a miniature contract, proving:

- the wiring: one durable send per decision slot;
- arm memory semantics: A keeps experience, B's prompt shows the
  ablated marker after the recorded ablation, C's experience section
  is frozen across its decisions, D never sends;
- malformed answers fall back (counted, never resent);
- the budget auto-stop stops the world with a partial report;
- every branch replays from recorded decisions (no port calls).
"""

from __future__ import annotations

import random
from pathlib import Path

from resonance_world.experimental_runtime.g1_v9.contract import G1V9Contract
from resonance_world.experimental_runtime.g1_v9.pilot import run_pilot
from resonance_world.experimental_runtime.g1_v9.send_ledger import (
    PersistentSendLedger,
    qualification_ledger_path,
)
from resonance_world.experimental_runtime.g1_v9.zai_transport import (
    QualificationTransportError,
)
from resonance_world.experimental_runtime.views import DecisionRequest, Observation

MINI_CONTRACT = G1V9Contract(
    acquisition_ticks=10,
    measurement_ticks=10,
    freeze_tick=5,
    decision_cadence=5,
    acquisition_checkpoints=(5, 10),
    measurement_checkpoints=(15, 20),
)


class ScriptedTransport:
    """Offline transport: ledger-metered, scripted answers, prompt capture."""

    model_id = "scripted"
    remaining = 999  # attribute form, mirrors what decide() prints

    def __init__(self, custody: Path, answers="AB", cap: int = 64):
        import hashlib

        campaign = hashlib.sha256(b"mini-campaign").hexdigest()
        custody.mkdir(parents=True, exist_ok=True)
        self._ledger = PersistentSendLedger(
            qualification_ledger_path(custody, campaign),
            send_cap=cap,
            authorization_id=campaign,
        )
        self.prompts: list[tuple[str, str]] = []
        self._answers = answers

    def send(self, label: str, prompt: str):
        self._ledger.record_attempt(label, label)
        self.prompts.append((label, prompt))
        answer = (
            self._answers(label, prompt)
            if callable(self._answers)
            else self._answers
        )
        return {"status": 200, "content": answer}


def _make_request(branch: str, tick: int, successes: int) -> DecisionRequest:
    observation = Observation(
        scenario_id="g1-v9-world-time-adaptation",
        branch_id=branch,
        tick=tick,
        public_state={"current_context": "context-1", "successes": successes},
        public_state_sha256="0" * 64,
        new_events=(),
    )
    return DecisionRequest(
        request_id=f"req-{branch}-{tick}",
        branch_id=branch,
        tick=tick,
        observation_seq=tick,
        observation=observation,
    )


def test_live_policy_parses_falls_back_and_hides_errors(tmp_path) -> None:
    from resonance_world.experimental_runtime.g1_v9.pilot import LiveGlmPolicy

    class FakeTransport:
        remaining = 99

        def __init__(self, answers):
            self.answers = list(answers)
            self.sent = 0

        def send(self, label, prompt):
            self.sent += 1
            answer = self.answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return {"status": 200, "content": answer}

    fake = FakeTransport([
        "BA",
        "I am unable to comply with that request.",
        QualificationTransportError("provider returned HTTP 429"),
        "AB",
    ])
    policy = LiveGlmPolicy(
        "adaptive",
        branch="test-branch",
        transport=fake,
        pacing_seconds=0,
        rng=random.Random(7),
    )

    successes = 0
    decisions = []
    for tick in range(4):
        successes += 1  # every decision succeeds (delta = 1 each time)
        decisions.append(
            policy.decide(_make_request("test-branch", tick, successes))
        )

    assert [d["ordering"] for d in decisions] == ["BA", "BA", "BA", "AB"]
    assert policy.malformed == 1
    assert policy.transport_errors == 1
    assert policy.fallbacks == 2
    assert fake.sent == 4  # never resent; exactly one send per decision
    assert set(decisions[0].keys()) == {"ordering", "context", "decided_at"}
    assert policy.snapshot()["log"][0]["outcome"] is True


def test_pilot_dress_rehearsal_full_mini_world(tmp_path) -> None:
    captured_prompts: list[tuple[str, str]] = []

    def factory():
        holder = ScriptedTransport(Path(tmp_path) / "ledger", answers="AB")
        original_send = holder.send

        def send(label, prompt):
            captured_prompts.append((label, prompt))
            return original_send(label, prompt)

        holder.send = send
        return holder

    report = run_pilot(
        custody_dir=Path(tmp_path) / "custody",
        credential_provider=lambda: "key",
        contract=MINI_CONTRACT,
        pacing_seconds=0,
        seed_material=b"mini-dress-rehearsal",
        transport_factory=factory,
    )

    # One send per decision slot: acquisition 2 + A 2 + B 2 + C 3; D never.
    assert report.sends_consumed == 9
    assert report.arms["A"]["own_decisions"] == 2
    assert report.arms["B"]["own_decisions"] == 2
    assert report.arms["C"]["own_decisions"] == 3
    assert report.arms["D"]["own_decisions"] == 4
    assert report.arms["D"]["port_calls"] == 4  # offline policy, zero sends
    assert report.malformed_answers == 0
    assert report.transport_errors == 0
    assert report.all_replays_matched is True
    assert report.leak_scan_clean is True
    # The mini world cannot satisfy the real-world validity counts.
    assert report.world_valid_for_analysis is False

    # Arm memory semantics visible in the prompts:
    b_prompts = [p for label, p in captured_prompts if ":arm-b-ablated:" in label]
    a_prompts = [p for label, p in captured_prompts if ":arm-a-adaptive:" in label]
    c_prompts = [p for label, p in captured_prompts if ":arm-c-frozen:" in label]
    d_labels = [label for label, _ in captured_prompts if ":arm-d-canonical:" in label]

    assert b_prompts, "arm B must send after the ablation point"
    assert "(memory ablated" in b_prompts[0]
    assert not any("(memory ablated" in p for p in a_prompts)
    assert a_prompts and "Your experience" in a_prompts[0]

    # Arm C: the experience section is frozen - identical across decisions.
    def experience_of(prompt: str) -> str:
        start = prompt.index("oldest first:") + len("oldest first:")
        return prompt[start : prompt.index("Current context")].strip()

    assert len(c_prompts) == 3
    assert experience_of(c_prompts[0]) == experience_of(c_prompts[1])
    assert experience_of(c_prompts[1]) == experience_of(c_prompts[2])
    assert experience_of(c_prompts[0]) != "(none yet)"

    assert d_labels == []  # arm D never calls the provider


def test_pilot_budget_auto_stop_stops_the_world(tmp_path) -> None:
    consumed = {"n": 0}

    def factory():
        holder = ScriptedTransport(Path(tmp_path) / "ledger", answers="AB", cap=5)
        original_send = holder.send

        def send(label, prompt):
            original_send(label, prompt)
            consumed["n"] += 1
            return {"status": 200, "content": "AB"}

        holder.send = send
        return holder

    report = run_pilot(
        custody_dir=Path(tmp_path) / "custody",
        credential_provider=lambda: "key",
        contract=MINI_CONTRACT,
        pacing_seconds=0,
        seed_material=b"mini-budget-seed-16b",
        transport_factory=factory,
    )

    assert report.budget_exhausted_early is True
    assert consumed["n"] == 5
    # The world stopped incomplete and says so.
    assert report.world_valid_for_analysis is False
    assert any("incomplete" in note for note in report.notes)
