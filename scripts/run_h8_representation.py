#!/usr/bin/env python3
"""Prepare or execute the preregistered H8 representation-boundary panel."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from h8_representation_core import EVIDENCE_SLOTS, canonical_bytes, chair_prompt, prepare

MODEL = "glm-5-turbo"
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MAX_TOKENS = 128
MAX_ATTEMPTS = 12
CONCURRENCY = 2
MIN_REQUEST_INTERVAL_SECONDS = 2.0
MAX_429_BACKOFF_SECONDS = 120.0
UNRESOLVED = "UNRESOLVED"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


class Client:
    def __init__(self, key: str) -> None:
        if not key.strip():
            raise ValueError("empty ZAI_API_KEY")
        self.key = key
        self.rng = random.Random(8150801)
        self.lock = threading.Lock()
        self.rate_lock = threading.Lock()
        self.next_request_at = 0.0

    def request_id(self, cell_id: str, phase: str, attempt: int) -> str:
        with self.lock:
            nonce = self.rng.getrandbits(64)
        return f"h8-{cell_id[-10:]}-{phase}-{attempt}-{nonce:016x}"

    def wait_for_slot(self) -> None:
        with self.rate_lock:
            now = time.monotonic()
            wait = max(0.0, self.next_request_at - now)
            if wait:
                time.sleep(wait)
            self.next_request_at = max(time.monotonic(), self.next_request_at) + MIN_REQUEST_INTERVAL_SECONDS

    def complete(self, *, cell_id: str, phase: str, prompt: str, actions: list[str], notices: list[str], evidence_slots: list[str]) -> dict[str, Any]:
        analyst = phase.startswith("analyst")
        expected = {"action", "notice_id", "evidence_ids", "finding"} if analyst else {"action", "notice_id", "evidence_ids"}
        system = (
            "Return exactly one JSON object with keys action, notice_id, evidence_ids"
            + (", finding" if analyst else "")
            + ". action must be one of " + ", ".join(actions) + (" or UNRESOLVED" if analyst else "")
            + ". notice_id must be one of " + ", ".join(notices) + (" or UNRESOLVED" if analyst else "")
            + ". evidence_ids must be an array containing only these evidence slots: " + ", ".join(evidence_slots) + "."
            + (" finding must be a concise string." if analyst else "") + " No other keys or text."
        )
        logs: list[dict[str, Any]] = []
        started_all = time.perf_counter()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request_id = self.request_id(cell_id, phase, attempt)
            body = {
                "model": MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "thinking": {"type": "disabled"}, "do_sample": True, "temperature": 0.8,
                "max_tokens": MAX_TOKENS, "stream": False, "response_format": {"type": "json_object"},
                "request_id": request_id,
            }
            request = Request(
                ENDPOINT,
                data=json.dumps(body, separators=(",", ":")).encode(),
                method="POST",
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                         "Accept-Language": "en-US,en", "User-Agent": "resonance-world-h8/0.1"},
            )
            self.wait_for_slot(); started = time.perf_counter(); retry_delay = min(8.0, 2.0 ** (attempt - 1))
            try:
                with urlopen(request, timeout=90.0) as response:
                    outer = json.loads(response.read().decode())
                if outer.get("model") != MODEL:
                    raise ValueError("model_drift")
                choices = outer.get("choices")
                if not isinstance(choices, list) or len(choices) != 1:
                    raise ValueError("choice_shape")
                payload = json.loads(choices[0].get("message", {}).get("content"))
                if not isinstance(payload, dict) or set(payload) != expected:
                    raise ValueError("output_keys")
                allowed_actions = actions + ([UNRESOLVED] if analyst else [])
                allowed_notices = notices + ([UNRESOLVED] if analyst else [])
                if payload["action"] not in allowed_actions:
                    raise ValueError("action_vocabulary")
                if payload["notice_id"] not in allowed_notices:
                    raise ValueError("notice_vocabulary")
                refs = payload["evidence_ids"]
                if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
                    raise ValueError("evidence_shape")
                if not all(ref in evidence_slots for ref in refs):
                    raise ValueError("evidence_vocabulary")
                if analyst and not isinstance(payload["finding"], str):
                    raise ValueError("finding_shape")
                logs.append({"attempt": attempt, "request_id": request_id, "status": "ok",
                             "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
                usage = outer.get("usage", {})
                return {"model": MODEL, "phase": phase, "request_id": request_id, "payload": payload,
                        "input_tokens": int(usage.get("prompt_tokens", 0)),
                        "output_tokens": int(usage.get("completion_tokens", 0)),
                        "attempt_log": logs,
                        "total_latency_ms": round((time.perf_counter() - started_all) * 1000, 3)}
            except HTTPError as exc:
                body_text = exc.read().decode(errors="replace")[:1000]
                logs.append({"attempt": attempt, "request_id": request_id, "status": f"http_{exc.code}",
                             "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
                if (exc.code != 429 and exc.code < 500) or attempt == MAX_ATTEMPTS:
                    raise RuntimeError(f"Z.AI HTTP {exc.code}: {body_text}") from exc
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After")
                    retry_delay = min(MAX_429_BACKOFF_SECONDS, 30.0 * (2.0 ** (attempt - 1)))
                    if retry_after:
                        try:
                            retry_delay = max(retry_delay, min(MAX_429_BACKOFF_SECONDS, float(retry_after)))
                        except ValueError:
                            pass
            except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                status = f"format_{exc.args[0]}" if isinstance(exc, ValueError) and exc.args else type(exc).__name__
                logs.append({"attempt": attempt, "request_id": request_id, "status": status,
                             "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError(f"Z.AI request failed after {attempt} attempts: {exc}") from exc
            time.sleep(retry_delay)
        raise AssertionError("unreachable")


def ledger_for(evidence: dict[str, Any]) -> Any:
    from resonance_world.authority import AuthorityGrant, AuthorityLedger

    ledger = AuthorityLedger()
    for raw in evidence["authority_grants"]:
        ledger.register(AuthorityGrant(**raw))
    return ledger


def majority(values: list[str], allowed_order: list[str]) -> str:
    counts = Counter(values); best = max(counts.values()); winners = {value for value, count in counts.items() if count == best}
    return next(value for value in allowed_order if value in winners)


def execute_cell(client: Client, ledger: Any, unit: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    notices = [notice["notice_id"] for notice in cell["authority_notices"]]
    if cell["protocol"] == "three_independent_neutral_calls_then_deterministic_majority":
        calls: list[dict[str, Any]] = []
        for index, prompt in enumerate(cell["direct_prompts"], start=1):
            call = client.complete(cell_id=cell["cell_id"], phase=f"direct{index}", prompt=prompt,
                                   actions=cell["actions"], notices=notices, evidence_slots=list(EVIDENCE_SLOTS))
            calls.append({**call, "member_id": cell["member_ids"][f"call_{index}"],
                          "prompt_sha256": cell["direct_prompt_sha256"][index - 1]})
        selected_action = majority([call["payload"]["action"] for call in calls], cell["actions"])
        selected_notice = majority([call["payload"]["notice_id"] for call in calls], notices)
        call_record: dict[str, Any] = {"direct_calls": calls}
    else:
        analyst_calls: list[dict[str, Any]] = []; reports: list[dict[str, Any]] = []
        for index, prompt in enumerate(cell["analyst_prompts"], start=1):
            call = client.complete(cell_id=cell["cell_id"], phase=f"analyst{index}", prompt=prompt,
                                   actions=cell["actions"], notices=notices, evidence_slots=list(EVIDENCE_SLOTS))
            role = cell["analyst_roles"][index - 1]
            analyst_calls.append({**call, "role": role, "member_id": cell["member_ids"][f"call_{index}"],
                                  "prompt_sha256": cell["analyst_prompt_sha256"][index - 1]})
            reports.append({"role": role, "member_id": cell["member_ids"][f"call_{index}"], **call["payload"]})
        prompt = chair_prompt(unit, member_id=cell["chair_member_id"], representation=cell["representation"], reports=reports)
        chair = client.complete(cell_id=cell["cell_id"], phase="chair", prompt=prompt,
                                actions=cell["actions"], notices=notices, evidence_slots=list(EVIDENCE_SLOTS))
        selected_action = chair["payload"]["action"]; selected_notice = chair["payload"]["notice_id"]
        call_record = {"analyst_calls": analyst_calls,
                       "chair_call": {**chair, "member_id": cell["chair_member_id"],
                                      "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()},
                       "chair_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}

    verification = ledger.verify(notice_id=selected_notice, organization_id=cell["organization_id"],
                                 scenario_id=f"{cell['unit_id']}-h8", action=f"execute:{cell['unit_id']}")
    return {"cell_id": cell["cell_id"], "unit_id": cell["unit_id"], "family": cell["family"], "arm": cell["arm"],
            "arm_order_rotation": cell["arm_order_rotation"], "representation_sha256": cell["representation_sha256"],
            "protocol": cell["protocol"], **call_record,
            "final_selection": {"action": selected_action, "notice_id": selected_notice},
            "authority_verification": verification.canonical_record()}


def execute(plan: dict[str, Any], evidence: dict[str, Any], key: str) -> dict[str, Any]:
    client = Client(key); ledger = ledger_for(evidence); units = {unit["unit_id"]: unit for unit in evidence["units"]}; completed: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(execute_cell, client, ledger, units[cell["unit_id"]], cell): cell for cell in plan["cells"]}
        for future in as_completed(futures):
            cell = futures[future]; completed[cell["cell_id"]] = future.result()
            print(f"H8_PROGRESS {len(completed)}/{len(plan['cells'])} {cell['arm']} {cell['unit_id']}", flush=True)
    cells = [completed[cell["cell_id"]] for cell in plan["cells"]]
    attempts = 0
    for cell in cells:
        calls = cell["direct_calls"] if "direct_calls" in cell else [*cell["analyst_calls"], cell["chair_call"]]
        attempts += sum(len(call["attempt_log"]) for call in calls)
    return {"schema": "h8-live-output-v0.1", "model": MODEL, "organization_cell_count": len(cells),
            "logical_model_call_count": len(cells) * 3, "physical_provider_attempt_count": attempts,
            "cells": cells, "production_historical_substrate_enabled": False}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--plane-e", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--request-plan", type=Path); parser.add_argument("--prepare-only", action="store_true"); args = parser.parse_args()
    evidence = load(args.plane_e); plan = prepare(evidence); args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.output_dir / "h8-request-plan.json"; plan_path.write_bytes(canonical_bytes(plan)); plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if args.request_plan:
        supplied = args.request_plan.read_bytes()
        if hashlib.sha256(supplied).hexdigest() != plan_sha or supplied != plan_path.read_bytes():
            raise SystemExit("supplied H8 request plan does not match deterministic regeneration")
    print(json.dumps({"request_plan_sha256": plan_sha, "organization_cell_count": len(plan["cells"]),
                      "logical_model_call_count": len(plan["cells"]) * 3}, sort_keys=True))
    if args.prepare_only: return 0
    key = os.environ.get("ZAI_API_KEY", "")
    if not key: raise SystemExit("ZAI_API_KEY is required unless --prepare-only is used")
    live = execute(plan, evidence, key); live_path = args.output_dir / "h8-live-output.json"; live_path.write_bytes(canonical_bytes(live))
    print(json.dumps({"live_output_sha256": hashlib.sha256(live_path.read_bytes()).hexdigest(),
                      "logical_model_call_count": live["logical_model_call_count"],
                      "physical_provider_attempt_count": live["physical_provider_attempt_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
