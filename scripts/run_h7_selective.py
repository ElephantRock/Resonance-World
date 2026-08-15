#!/usr/bin/env python3
"""Prepare or execute the preregistered H7 selective-state routing panel."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from h1_runtime_core import cb
from h6_relevance_core import EVIDENCE_SLOTS
from h7_selective_core import chair_prompt, prepare
from run_h6_relevance import Client as H6Client
from resonance_world.authority import AuthorityGrant, AuthorityLedger

MODEL = "glm-5-turbo"
CONCURRENCY = 2


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict): raise ValueError("expected JSON object")
    return value


def ledger_for(evidence: dict[str, Any]) -> AuthorityLedger:
    ledger = AuthorityLedger()
    for raw in evidence["authority_grants"]: ledger.register(AuthorityGrant(**raw))
    return ledger


class Client(H6Client):
    def request_id(self, cell_id: str, phase: str, attempt: int) -> str:
        with self.lock:
            nonce = self.rng.getrandbits(64)
        return f"h7-{cell_id[-10:]}-{phase}-{attempt}-{nonce:016x}"


def execute_cell(client: Client, ledger: AuthorityLedger, cell: dict[str, Any]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []; reports: list[dict[str, Any]] = []
    for i in range(2):
        call = client.complete(cell["organizational_cell_id"], f"analyst{i + 1}", cell["analyst_prompts"][i],
                               cell["actions"], cell["candidate_notices"], cell["analyst_partitions"][i])
        calls.append({**call, "role": cell["analyst_roles"][i], "member_id": cell["analyst_member_ids"][i],
                      "delivered_evidence_slots": cell["analyst_partitions"][i], "prompt_sha256": cell["analyst_prompt_sha256"][i]})
        reports.append({"role": cell["analyst_roles"][i], "member_id": cell["analyst_member_ids"][i], **call["payload"]})
    prompt = chair_prompt(cell, reports)
    chair = client.complete(cell["organizational_cell_id"], "chair", prompt, cell["actions"],
                            cell["candidate_notices"], list(EVIDENCE_SLOTS))
    selected = chair["payload"]
    verification = ledger.verify(notice_id=selected["notice_id"], organization_id=cell["organization_id"],
        scenario_id=f"{cell['unit_id']}-h7", action=f"execute:{cell['unit_id']}-h7")
    public = {key: value for key, value in cell.items() if key != "analyst_prompts"}
    return {**public, "analyst_calls": calls,
            "chair_call": {**chair, "role": "chair", "member_id": cell["chair_member_id"],
                           "delivered_evidence_slots": list(EVIDENCE_SLOTS),
                           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()},
            "chair_prompt": prompt, "authority_verification": verification.canonical_record(),
            "execution_acknowledgement": {"schema": "h7-execution-acknowledgement-v0.1",
                "organizational_cell_id": cell["organizational_cell_id"], "selected_action": selected["action"],
                "selected_notice_id": selected["notice_id"], "authority_verified": verification.verified}}


def execute(plan: dict[str, Any], evidence: dict[str, Any], key: str) -> dict[str, Any]:
    client, ledger = Client(key), ledger_for(evidence); completed: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(execute_cell, client, ledger, cell): cell for cell in plan["cells"]}
        for future in as_completed(futures):
            cell = futures[future]; completed[cell["organizational_cell_id"]] = future.result()
            print(f"H7_PROGRESS {len(completed)}/{len(plan['cells'])} {cell['replicate']} {cell['arm']} {cell['unit_id']}", flush=True)
    cells = [completed[cell["organizational_cell_id"]] for cell in plan["cells"]]
    attempts = sum(len(call["attempt_log"]) for cell in cells for call in [*cell["analyst_calls"], cell["chair_call"]])
    return {"schema": "h7-live-output-v0.1", "model": MODEL, "organization_cell_count": len(cells),
            "logical_model_call_count": len(cells) * 3, "physical_provider_attempt_count": attempts, "cells": cells,
            "production_historical_substrate_enabled": False}


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--plane-e", type=Path, required=True); p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--prepare-only", action="store_true"); a = p.parse_args(); evidence = load(a.plane_e); plan = prepare(evidence)
    a.output_dir.mkdir(parents=True, exist_ok=True); plan_path = a.output_dir / "h7-request-plan.json"; plan_path.write_bytes(cb(plan))
    print(json.dumps({"request_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                      "organization_cell_count": len(plan["cells"]), "logical_model_call_count": len(plan["cells"]) * 3}, sort_keys=True))
    if a.prepare_only: return 0
    key = os.environ.get("ZAI_API_KEY", "")
    if not key: raise SystemExit("ZAI_API_KEY is required unless --prepare-only is used")
    live = execute(plan, evidence, key); live_path = a.output_dir / "h7-live-output.json"; live_path.write_bytes(cb(live))
    print(json.dumps({"live_output_sha256": hashlib.sha256(live_path.read_bytes()).hexdigest(),
                      "logical_model_call_count": live["logical_model_call_count"],
                      "physical_provider_attempt_count": live["physical_provider_attempt_count"]}, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
