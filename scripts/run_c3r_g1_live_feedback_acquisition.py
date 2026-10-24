"""Live, no-repair C3R G1 acquisition study: active binary-feedback vs fixed-feedback vs no-feedback.

Each context has one private five-bit program. The model chooses probes, receives at
most one bit of independent-world feedback per probe, proposes a new policy, and
uses the persisted policy on a fresh hidden-target task. The evaluator is
authoritative; public diagnostics contain no private programs, policy text, or
raw provider responses. A technical acquisition result is NOT scientific promotion.
"""
from __future__ import annotations
import argparse
import os
import collections
import itertools
import json
import random
import re
import secrets
import statistics
import time
from pathlib import Path

from run_c3r_g1_model_induced_five_step_live import MODEL, _execute, _grammar, _task
from resonance_world.c3r_g1_zai_transport import ZaiStandardModelPort, PhysicalSendLedger

CODES = tuple("".join(p) for p in itertools.product("AB", repeat=5))
FIXED = (5, 10, 16, 21, 26)
ARMS = ("active_feedback", "fixed_feedback", "no_feedback")
STEPS = 5
SCHEMA = "c3r-g1-live-feedback-acquisition-v0.3"



class RedactedJournal:
    """Durable per-context journal. Never records hidden programs, model text or feedback bits."""

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL prevents rerunning the same logical experimental unit in this workspace.
        self.fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.reserved_attempts = 0
        self.completed_attempts = 0

    def record(self, event):
        safe = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        os.write(self.fd, safe)
        os.fsync(self.fd)

    def reserve(self, label):
        self.reserved_attempts += 1
        self.record({"event": "request_reserved", "slot": label, "ordinal": self.reserved_attempts})

    def complete(self, label, status, usage, elapsed, http_status=None):
        self.completed_attempts += 1
        self.record({"event": "request_completed", "slot": label, "status": status,
                     "reported_completion_tokens": usage if type(usage) is int else None,
                     "http_status": http_status,
                     "elapsed_seconds": round(elapsed, 3)})

    def close(self):
        os.close(self.fd)


def public_view(family, task):
    # Candidate results are public, but neither their generating policies nor
    # the private actual result are disclosed to the model.
    results = [_execute(family, task, c) for c in CODES]
    if len(set(results)) != len(CODES):
        raise ValueError("ambiguous test inputs")
    sorted_rows = sorted(zip(results, CODES), key=lambda row: int(row[0]) if family == "arithmetic" else row[0])
    ranked = [result for result, _ in sorted_rows]
    # All candidate programs and outputs are publicly computable; none is the
    # hidden program label. Supplying the deterministic table avoids pointless
    # repeated simulation of 32 programs inside the model.
    return {"family": family, "task": task, "operation_grammar": _grammar(family),
            "thresholds": ranked,
            "ranked_candidates": [[code, result] for result, code in sorted_rows],
            "legal_probes": [f"ge-{i:02d}" for i in range(1, 32)],
            "feedback_rule": "ge-N is true iff the secret output rank is >= N, using zero-based thresholds. Each answer exposes at most one bit."}


def prompt_for(kind, view, observations):
    if kind == "probe":
        instructions = ("Choose a threshold that approximately HALVES the remaining possible ranks. "
                        "Use prior true/false answers to narrow the hidden rank (0..31). "
                        "Return exactly ge-NN, N=01..31, without explanation.")
    else:
        instructions = ("Use observed threshold answers to identify which row of ranked_candidates "
                        "can be the hidden program. The public candidate list is not a secret "
                        "answer. Return ONLY its five-letter A/B policy, e.g. ABBAA.")
    return json.dumps({"kind": kind, "instructions": instructions, "public_world": view,
                       "observations": observations}, sort_keys=True, separators=(",", ":"))


def ask(prompt, key, journal, label, max_tokens=8192):
    """Exactly one execution per successful call; retry only explicit HTTP 429.

    Every physical retry is independently reserved and fsynced. No retry on
    transport ambiguity, timeout, HTTP 5xx, or an accepted response.
    """
    for retry in range(3):
        attempt_label = f"{label}:attempt:{retry}"
        journal.reserve(attempt_label)
        started = time.monotonic()
        answer, status, usage = None, "provider_error", None
        port = None
        try:
            port = ZaiStandardModelPort(
                api_key=key, model_id=MODEL, ledger=PhysicalSendLedger(1),
                enabled=True, route="coding", reasoning_effort="high",
                max_tokens=max_tokens, timeout_seconds=240,
            )
            completed = port.complete_prompt(prompt)
            if completed.model_id != MODEL or completed.finish_reason != "stop":
                status, usage = "non_stop", completed.completion_tokens_reported
            else:
                answer, status, usage = completed.output.strip(), "accepted", completed.completion_tokens_reported
        except Exception as exc:
            status = "provider_error_" + type(exc).__name__[:35]
        elapsed = time.monotonic() - started
        code = (port.ledger.records[-1].http_status
                if port is not None and port.ledger.records else None)
        journal.complete(attempt_label, status, usage, elapsed, code)
        if code == 429 and retry < 2:
            # Definitely rejected requests; do not retry uncertain/timeouts.
            delay = (60, 120)[retry]
            journal.record({"event": "provider_backoff", "slot": label,
                            "retry": retry + 1, "http_status": code,
                            "delay_seconds": delay})
            time.sleep(delay)
            continue
        return answer, status, usage, elapsed
    raise AssertionError("unreachable retry limit")


def one_arm(context, arm, key, journal):
    family, source_task, holdout_task, private_code = context
    view = public_view(family, source_task)
    ranked = view["thresholds"]
    actual = _execute(family, source_task, private_code)
    actual_rank = ranked.index(actual)
    observed = []
    statuses = []
    token_total = 0
    valid_sends = 0
    latency = 0.0
    for i in range(STEPS):
        # The controls must not spend calls soliciting choices they discard.
        # Fixed feedback is a predefined threshold schedule; no-feedback sees
        # no graded observations. Active alone solicits model-chosen probes.
        if arm == "no_feedback":
            observed.append({"step": i, "status": "no_observation"})
            statuses.append("withheld")
            continue
        if arm == "fixed_feedback":
            idx = FIXED[i]
        else:
            proposal, state, usage, elapsed = ask(
                prompt_for("probe", view, observed), key, journal,
                f"{arm}:probe:{i}", max_tokens=8192)
            latency += elapsed
            token_total += usage or 0
            valid_sends += state == "accepted"
            if state.startswith("provider_error"):
                raise RuntimeError("provider rejected active probe")
            if state == "accepted" and re.fullmatch(r"ge-(?:0[1-9]|[12][0-9]|3[01])", proposal or ""):
                idx = int(proposal[-2:])
            else:
                statuses.append("invalid_probe" if state == "accepted" else state)
                observed.append({"step": i, "status": "no_observation"})
                continue
        feedback = actual_rank >= idx
        observed.append({"step": i, "probe_id": f"ge-{idx:02d}",
                         "status": "observed", "feedback": feedback})
        statuses.append("observed")
    proposal, state, usage, elapsed = ask(prompt_for("capsule", view, observed), key, journal, f"{arm}:capsule", max_tokens=16384)
    latency += elapsed
    token_total += usage or 0
    valid_sends += state == "accepted"
    if state.startswith("provider_error"):
        raise RuntimeError("provider rejected capsule; ending this experimental unit")
    correct_format = bool(state == "accepted" and re.fullmatch(r"[AB]{5}", proposal or ""))
    source_correct = bool(correct_format and proposal == private_code)
    # Holdout uses a new model completion with NO source task/examples/transcript.
    if correct_format:
        hold_prompt = ("Execute the following exact five-step A/B procedure IN ORDER on "
                       "the NEW input. Return only the final result, no reasoning.\n"
                       + _grammar(family) + "\n"
                       + "Procedure: " + proposal + "\n"
                       + "New input: " + json.dumps(holdout_task, sort_keys=True))
        actual_holdout = _execute(family, holdout_task, private_code)
        hold_ans, hold_state, hold_usage, hold_latency = ask(hold_prompt, key, journal, f"{arm}:holdout", max_tokens=8192)
        token_total += hold_usage or 0
        valid_sends += hold_state == "accepted"
        latency += hold_latency
        if hold_state.startswith("provider_error"):
            raise RuntimeError("provider rejected holdout; ending this experimental unit")
        hold_correct = bool(hold_state == "accepted" and hold_ans == actual_holdout)
    else:
        hold_state = "not_sent_invalid_capsule"
        hold_correct = False
    return {"arm": arm, "family": family,
            "probe_status_counts": dict(collections.Counter(statuses)),
            "source_status": state, "source_valid": correct_format,
            "source_correct": source_correct, "holdout_status": hold_state,
            "holdout_correct": hold_correct,
            "logical_slots": (7 if arm == "active_feedback" else 2),
            "planned_calls_reached": (6 if arm == "active_feedback" else 1) + int(correct_format),
            "successful_model_responses": valid_sends,
            "reported_completion_tokens": token_total,
            "elapsed_seconds": round(latency, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", choices=[f"{i:02d}" for i in range(1, 7)])
    ap.add_argument("--position", type=int, choices=range(4))
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise SystemExit("reruns forbidden: new source units require a fresh unique campaign")
    key = os.environ.get("C3R_ZAI_API_KEY", "")
    if not key:
        raise SystemExit("credential missing: zero sends")
    journal = RedactedJournal(args.out)
    try:
        if args.preflight:
            view = public_view("arithmetic", _task(random.SystemRandom(), "arithmetic"))
            _, state, _, _ = ask(prompt_for("probe", view, []), key, journal, "provider_preflight")
            journal.record({"event": "provider_preflight_result", "status": state})
            print(json.dumps({"provider_preflight": state}), flush=True)
            if state != "accepted":
                raise SystemExit("provider preflight failed; no experimental units dispatched")
            return
        if args.cohort is None or args.position is None:
            raise SystemExit("cohort and position required for acquisition")
        pos = args.position
        family = "arithmetic" if pos < 2 else "text"
        rng = random.SystemRandom()
        source = _task(rng, family)
        holdout = _task(rng, family)
        while holdout == source:
            holdout = _task(rng, family)
        context = (family, source, holdout, secrets.choice(CODES))
        context_id = f"{args.cohort}-{pos:02d}"
        journal.record({"event": "context_started", "schema": SCHEMA,
                        "context_id": context_id, "family": family, "model": MODEL,
                        "reasoning_effort": "high", "max_tokens_probe": 8192,
                        "max_tokens_capsule": 16384, "max_tokens_holdout": 8192,
                        "planned_slots": 11, "scientific_acceptance": False})
        rows = []
        terminated = False
        for arm in ARMS:
            if terminated:
                result = {"arm": arm, "family": family, "source_valid": False,
                          "source_correct": False, "holdout_correct": False,
                          "holdout_status": "not_attempted_after_provider_error",
                          "source_status": "not_attempted_after_provider_error",
                          "analyzable": False}
            else:
                try:
                    result = one_arm(context, arm, key, journal)
                    result["analyzable"] = True
                except RuntimeError:
                    # Preserve the aborted unit and do not hide loss of a
                    # treatment arm. No posthoc denominator exclusions.
                    result = {"arm": arm, "family": family, "source_valid": False,
                              "source_correct": False, "holdout_correct": False,
                              "holdout_status": "provider_error",
                              "source_status": "provider_error", "analyzable": False}
                    terminated = True
            result["context_id"] = context_id
            rows.append(result)
            journal.record({"event": "arm_result", **result})
        summary = {"event": "context_complete", "schema": SCHEMA,
                   "context_id": context_id, "family": family,
                   "rows_complete": len(rows),
                   "request_reservations": journal.reserved_attempts,
                   "request_completions": journal.completed_attempts,
                   "physical_sends_verified": False,
                   "complete_arms": sum(r["analyzable"] for r in rows),
                   "by_arm": {row["arm"]: {
                       "source_valid": row["source_valid"],
                       "source_correct": row["source_correct"],
                       "holdout_correct": row["holdout_correct"]}
                       for row in rows},
                   "scientific_acceptance": False,
                   "model_weight_updates_proven": False,
                   "time_delayed_retention_proven": False}
        journal.record(summary)
        print(json.dumps({"context_id": context_id, "by_arm": summary["by_arm"],
                          "request_reservations": journal.reserved_attempts}, sort_keys=True), flush=True)
    finally:
        journal.close()


if __name__ == "__main__":
    main()
