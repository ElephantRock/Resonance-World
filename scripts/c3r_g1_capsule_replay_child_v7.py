"""Fresh-interpreter G1 capsule replay. No source transcript is supplied to the model.

This process receives only the saved five-letter policy and new input in its
model prompt. A private oracle is held in the process for offline grading only.
Raw model responses, hidden policies and oracle outputs are NEVER printed or
uploaded. Its append-only journal is fsynced after every attempt.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from run_c3r_g1_live_feedback_acquisition import RedactedJournal, ask
from run_c3r_g1_model_induced_five_step_live import _execute, _grammar

def replay(capsule_file: Path, wave: int, result_file: Path, audit_file: Path):
    if wave not in (1, 2):
        raise ValueError("unsupported replay wave")
    capsule = json.loads(capsule_file.read_text(encoding="utf-8"))
    family, learned, truth = (capsule[key] for key in ("family", "policy", "private_program"))
    if family not in ("arithmetic", "text") or learned is None or len(learned) != 5 or set(learned) - set("AB"):
        raise ValueError("invalid sealed capsule")
    task = capsule["holdouts"][wave-1]
    applied = _execute(family, task, learned)
    expected = _execute(family, task, truth)
    # This prompt is the ONLY information supplied to the model. It contains
    # no oracle output, acquisition task, graded events or secret truth policy.
    prompt = (
        "New independent session. Execute this EXACT saved five-step A/B "
        "procedure. Return only the final result without a derivation.\n"
        + "Operations: " + _grammar(family) + "\n"
        + "Saved capsule: " + learned + "\n"
        + "New task: " + json.dumps(task, sort_keys=True)
    )
    journal = RedactedJournal(audit_file, append=True)
    try:
        response, state, usage, elapsed = ask(prompt, os.environ["C3R_ZAI_API_KEY"], journal,
                                               f"cross_process_holdout:{wave}", max_tokens=8192)
    finally:
        journal.close()
    verdict = {"wave": wave, "source_capsule_valid": True,
               "deterministic_correct": (applied == expected),
               "model_execution_correct": (state == "accepted" and response == expected),
               "model_execution_status": state, "reported_completion_tokens": usage,
               "elapsed_seconds": round(elapsed, 3),
               "source_prompt_visible": False, "grader_secret_visible_in_model_prompt": False,
               "pid": os.getpid()}
    if result_file.exists():
        raise FileExistsError("never overwrite fresh interpreter verdict")
    fd = os.open(str(result_file), os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    try:
        payload = (json.dumps(verdict, sort_keys=True) + "\n").encode()
        os.write(fd,payload);os.fsync(fd)
    finally:
        os.close(fd)

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--capsule", type=Path, required=True)
    p.add_argument("--wave", type=int, choices=[1,2], required=True)
    p.add_argument("--result", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    args=p.parse_args()
    replay(args.capsule,args.wave,args.result,args.audit)
