"""G1 v8: encrypted model-authored policies, delayed new-runner retention.
Only ciphertext and redacted judgments are published; no weight-change claim.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from run_c3r_g1_live_persistence_v7 import (
    ARMS, CODES, FIXED, MODEL, RedactedJournal, _execute, _task,
    ask, prompt_for, public_view,
)

SCHEMA = "c3r-g1-delayed-cross-run-v0.1"
HEADER = b"RWG1V8\x00"
AAD = b"RW-G1-V8-SEALED-CAPSULE"
DELAY_SECONDS = 1800

def encryption_key(secret: str) -> bytes:
    if not secret:
        raise ValueError("empty provider secret")
    return hashlib.sha256(b"resonance-g1-v8-artifact-key\x00" + secret.encode()).digest()

def sealed_write(path: Path, private: dict, secret: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nonce = os.urandom(12)
    raw = json.dumps(private, separators=(",", ":"), sort_keys=True).encode()
    blob = HEADER + nonce + AESGCM(encryption_key(secret)).encrypt(nonce, raw, AAD)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)

def sealed_read(path: Path, secret: str) -> dict:
    blob = path.read_bytes()
    if not blob.startswith(HEADER) or len(blob) < len(HEADER) + 12 + 16:
        raise ValueError("bad encrypted capsule envelope")
    nonce = blob[len(HEADER):len(HEADER)+12]
    return json.loads(AESGCM(encryption_key(secret)).decrypt(
        nonce, blob[len(HEADER)+12:], AAD))

def source(cohort: str, position: int, folder: Path, secret: str) -> None:
    family = "arithmetic" if position < 2 else "text"
    rng = random.SystemRandom()
    src = _task(rng, family)
    holdouts = []
    while len(holdouts) < 2:
        task = _task(rng, family)
        if task != src and task not in holdouts:
            holdouts.append(task)
    target = secrets.choice(CODES)
    view = public_view(family, src)
    actual_rank = view["thresholds"].index(_execute(family, src, target))
    context_id = f"{cohort}-{position:02d}"
    journal = RedactedJournal(folder / "source.jsonl")
    policies = {}
    try:
        journal.record({"event": "source_started", "schema": SCHEMA, "context_id": context_id,
                        "model": MODEL, "family": family, "source_oracle_hidden": True})
        for arm in ARMS:
            observations = []
            for i in range(5):
                if arm == "no_feedback":
                    observations.append({"step": i, "status": "no_observation"})
                    continue
                if arm == "fixed_feedback":
                    idx = FIXED[i]
                else:
                    proposal, state, _, _ = ask(
                        prompt_for("probe", view, observations), secret,
                        journal, f"{arm}:probe:{i}", max_tokens=8192)
                    match = re.fullmatch(r"ge-(?:0[1-9]|[12][0-9]|3[01])", proposal or "")
                    if state != "accepted" or not match:
                        observations.append({"step": i, "status": "no_observation"})
                        continue
                    idx = int(proposal[-2:])
                observations.append({"step": i, "probe_id": f"ge-{idx:02d}",
                                     "status": "observed", "feedback": actual_rank >= idx})
            policy, state, _, _ = ask(prompt_for("capsule", view, observations), secret,
                                      journal, f"{arm}:capsule", max_tokens=16384)
            accepted = state == "accepted" and bool(re.fullmatch(r"[AB]{5}", policy or ""))
            policies[arm] = policy if accepted else None
            journal.record({"event": "source_arm", "arm": arm, "valid": accepted,
                            "correct": bool(accepted and policy == target),
                            "source_status": state})
        sealed_write(folder / "capsule.aes", {
            "schema": SCHEMA, "context_id": context_id, "family": family,
            "acquired_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "private_program": target, "policies": policies, "holdouts": holdouts,
        }, secret)
        journal.record({"event": "source_complete", "context_id": context_id,
                        "encrypted_capsule_persisted": True, "policies": len(policies)})
        print(json.dumps({"stage": "source", "context_id": context_id, "sealed": True}), flush=True)
    finally:
        journal.close()

def replay(folder: Path, secret: str, delay_seconds: int = DELAY_SECONDS) -> None:
    private = sealed_read(folder / "capsule.aes", secret)
    if private.get("schema") != SCHEMA or set(private.get("policies", {})) != set(ARMS):
        raise ValueError("invalid capsule schema or randomized arms")
    acquired = dt.datetime.fromisoformat(private["acquired_at"])
    elapsed = (dt.datetime.now(dt.timezone.utc) - acquired).total_seconds()
    if elapsed < delay_seconds:
        time.sleep(delay_seconds - elapsed)
    actual_delay = (dt.datetime.now(dt.timezone.utc) - acquired).total_seconds()
    if actual_delay < delay_seconds:
        raise AssertionError("insufficient real elapsed retention delay")
    context_id = private["context_id"]
    journal = RedactedJournal(folder / "retention.jsonl")
    try:
        journal.record({"event": "retention_started", "schema": SCHEMA,
                        "context_id": context_id, "delay_seconds": round(actual_delay, 1),
                        "recovered_from_encrypted_artifact": True,
                        "independent_workflow_job": True})
        for arm in ARMS:
            policy = private["policies"][arm]
            good = policy in CODES if policy is not None else False
            results = []
            for wave in (1, 2):
                if not good:
                    verdict = {"model_execution_status": "not_sent_invalid_capsule",
                               "deterministic_correct": False, "model_execution_correct": False}
                else:
                    capsule_path = folder / f"private-{arm}-{wave}.json"
                    fd = os.open(str(capsule_path), os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
                    try:
                        os.write(fd, json.dumps({"family": private["family"], "policy": policy,
                                                 "private_program": private["private_program"],
                                                 "holdouts": private["holdouts"]}).encode())
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    verdict_path = folder / f"private-verdict-{arm}-{wave}.json"
                    try:
                        outcome = subprocess.run(
                            [sys.executable, str(Path(__file__).with_name(
                                "c3r_g1_capsule_replay_child_v7.py")),
                             "--capsule", str(capsule_path), "--wave", str(wave),
                             "--result", str(verdict_path),
                             "--audit", str(folder / "retention.jsonl")],
                            capture_output=True, text=True, check=False, timeout=720)
                        if outcome.returncode == 0 and verdict_path.exists():
                            verdict = json.loads(verdict_path.read_text())
                        else:
                            verdict = {"model_execution_status": "replay_error",
                                       "deterministic_correct": False, "model_execution_correct": False}
                    finally:
                        capsule_path.unlink(missing_ok=True)
                        verdict_path.unlink(missing_ok=True)
                journal.record({"event": "retention_wave", "context_id": context_id,
                                "arm": arm, "wave": wave,
                                "status": verdict["model_execution_status"],
                                "deterministic_correct": verdict["deterministic_correct"],
                                "model_correct": verdict["model_execution_correct"]})
                results.append(verdict)
            journal.record({"event": "retention_arm", "context_id": context_id,
                            "arm": arm, "both_deterministic_correct": all(
                                x["deterministic_correct"] for x in results),
                            "both_model_correct": all(
                                x["model_execution_correct"] for x in results)})
        journal.record({"event": "retention_complete", "context_id": context_id,
                        "completed_arms": 3, "delay_seconds": round(actual_delay, 1)})
        print(json.dumps({"stage": "retention", "context_id": context_id,
                          "delay_seconds": round(actual_delay, 1), "arms": 3}), flush=True)
    finally:
        journal.close()

def selftest() -> None:
    import tempfile
    from cryptography.exceptions import InvalidTag
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        private = {"schema": SCHEMA, "private_program": "ABABA",
                   "holdouts": [{"value": "private"}]}
        sealed_write(root / "seal.aes", private, "fixture-provider-secret")
        assert sealed_read(root / "seal.aes", "fixture-provider-secret") == private
        assert b"ABABA" not in (root / "seal.aes").read_bytes()
        try:
            sealed_read(root / "seal.aes", "wrong-secret")
            raise AssertionError("invalid encryption key accepted")
        except InvalidTag:
            pass
        j = RedactedJournal(root / "source.jsonl")
        j.record({"event": "test"})
        j.close()
        assert json.loads((root / "source.jsonl").read_text())["event"] == "test"
    print("v8 encrypted capsule and redacted journal: pass, zero provider calls")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["selftest", "source", "replay"])
    parser.add_argument("--cohort", choices=[f"{x:02d}" for x in range(1, 7)])
    parser.add_argument("--position", type=int, choices=range(4))
    parser.add_argument("--folder", type=Path)
    args = parser.parse_args()
    if args.stage == "selftest":
        selftest()
        return
    secret = os.getenv("C3R_ZAI_API_KEY", "")
    if not secret:
        raise SystemExit("missing provider key; no sends")
    if args.folder is None or args.cohort is None or args.position is None:
        raise SystemExit("cohort, position and folder required")
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise SystemExit("rerun blocked; protects experimental unit uniqueness")
    args.folder.mkdir(parents=True, exist_ok=True)
    if args.stage == "source":
        source(args.cohort, args.position, args.folder, secret)
    else:
        replay(args.folder, secret)

if __name__ == "__main__":
    main()
