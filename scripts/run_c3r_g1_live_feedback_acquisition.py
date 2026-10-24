"""Live, no-repair C3R G1 acquisition study: active binary-feedback vs fixed-feedback vs no-feedback.

Each context has one private five-bit program. The model chooses probes, receives at
most one bit of independent-world feedback per probe, proposes a new policy, and
uses the persisted policy on a fresh hidden-target task. The evaluator is
authoritative; public diagnostics contain no private programs, policy text, or
raw provider responses. A technical acquisition result is NOT scientific promotion.
"""
from __future__ import annotations
import argparse
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
SCHEMA = "c3r-g1-live-feedback-acquisition-v0.1"


def public_view(family, task):
    # Candidate results are public, but neither their generating policies nor
    # the private actual result are disclosed to the model.
    results = [_execute(family, task, c) for c in CODES]
    if len(set(results)) != len(CODES):
        raise ValueError("ambiguous test inputs")
    ranked = sorted(results, key=int if family == "arithmetic" else str)
    return {"family": family, "task": task, "operation_grammar": _grammar(family),
            "thresholds": ranked, "legal_probes": [f"ge-{i:02d}" for i in range(1, 32)],
            "feedback_rule": "ge-N is true when the private final output is >= thresholds[N]; comparison numeric for arithmetic, lexicographic for text."}


def prompt_for(kind, view, observations):
    if kind == "probe":
        instructions = ("Select exactly ONE legal threshold probe, e.g. ge-16. "
                        "You have five total probes and should maximize what you learn "
                        "from the feedback. Return only ge-NN.")
    else:
        instructions = ("Infer the hidden five-choice A/B program using ONLY the "
                        "public task and observed binary feedback. Return EXACTLY "
                        "five A/B letters, e.g. ABBAA. No explanation.")
    return json.dumps({"kind": kind, "instructions": instructions, "public_world": view,
                       "observations": observations}, sort_keys=True, separators=(",", ":"))


def ask(prompt, key):
    started = time.monotonic()
    try:
        port = ZaiStandardModelPort(
            api_key=key, model_id=MODEL, ledger=PhysicalSendLedger(1),
            enabled=True, route="coding", reasoning_effort="high",
            max_tokens=4096, timeout_seconds=150,
        )
        completed = port.complete_prompt(prompt)
        if completed.model_id != MODEL or completed.finish_reason != "stop":
            return None, "non_stop", completed.completion_tokens_reported, time.monotonic() - started
        return completed.output.strip(), "accepted", completed.completion_tokens_reported, time.monotonic() - started
    except Exception as exc:
        # Never preserve raw provider errors, response bodies, or credentials.
        safe = type(exc).__name__
        return None, "provider_error_" + safe[:35], None, time.monotonic() - started


def one_arm(context, arm, key):
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
        proposal, state, usage, elapsed = ask(prompt_for("probe", view, observed), key)
        latency += elapsed
        token_total += usage or 0
        valid_sends += state == "accepted"
        if arm == "fixed_feedback":
            idx = FIXED[i]
        elif state == "accepted" and re.fullmatch(r"ge-(?:0[1-9]|[12][0-9]|3[01])", proposal or ""):
            idx = int(proposal[-2:])
        else:
            statuses.append("invalid_probe" if state == "accepted" else state)
            observed.append({"step": i, "status": "no_observation"})
            continue
        feedback = (actual_rank >= idx) if arm != "no_feedback" else None
        observed.append({"step": i, "probe_id": f"ge-{idx:02d}",
                         "status": "observed" if feedback is not None else "withheld",
                         "feedback": feedback})
        statuses.append("observed" if feedback is not None else "withheld")
    proposal, state, usage, elapsed = ask(prompt_for("capsule", view, observed), key)
    latency += elapsed
    token_total += usage or 0
    valid_sends += state == "accepted"
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
        hold_ans, hold_state, hold_usage, hold_latency = ask(hold_prompt, key)
        token_total += hold_usage or 0
        valid_sends += hold_state == "accepted"
        latency += hold_latency
        hold_correct = bool(hold_state == "accepted" and hold_ans == actual_holdout)
    else:
        hold_state = "not_sent_invalid_capsule"
        hold_correct = False
    return {"arm": arm, "family": family,
            "probe_status_counts": dict(collections.Counter(statuses)),
            "source_status": state, "source_valid": correct_format,
            "source_correct": source_correct, "holdout_status": hold_state,
            "holdout_correct": hold_correct, "logical_slots": 7,
            "physical_sends_attempted": 6 + int(correct_format),
            "successful_model_responses": valid_sends,
            "reported_completion_tokens": token_total,
            "elapsed_seconds": round(latency, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", choices=[f"{i:02d}" for i in range(1, 7)], required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    import os
    key = os.environ.get("C3R_ZAI_API_KEY", "")
    if not key:
        raise SystemExit("credential missing: zero sends")
    rng = random.SystemRandom()
    rows = []
    for pos in range(4):
        family = "arithmetic" if pos < 2 else "text"
        context = (family, _task(rng, family), _task(rng, family), secrets.choice(CODES))
        for arm in ARMS:
            result = one_arm(context, arm, key)
            result["context_id"] = f"{args.cohort}-{pos:02d}"
            rows.append(result)
    summary = {"schema": SCHEMA, "cohort": args.cohort, "model": MODEL,
               "reasoning_effort": "high", "max_tokens": 4096,
               "contexts": 4, "rows": rows, "planned_logical_slots": 84,
               "actual_physical_sends": sum(x["physical_sends_attempted"] for x in rows),
               "by_arm": {a: {"source_correct": sum(x["source_correct"] for x in rows if x["arm"] == a),
                              "holdout_correct": sum(x["holdout_correct"] for x in rows if x["arm"] == a),
                              "source_valid": sum(x["source_valid"] for x in rows if x["arm"] == a)}
                          for a in ARMS},
               "scientific_acceptance": False,
               "model_weight_updates_proven": False,
               "time_delayed_retention_proven": False,
               "note": "Model-generated adaptive probes and model-generated policies, no repair. Synthetic benchmark; new inputs, fresh completion."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # No private program, raw response, or raw prompt is written.
    args.out.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("cohort", "by_arm", "actual_physical_sends")}, sort_keys=True))


if __name__ == "__main__":
    main()
