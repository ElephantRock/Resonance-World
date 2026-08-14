#!/usr/bin/env python3
"""Prepare and execute the preregistered H4 stochastic successor panel."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from h1_runtime_core import CG, cb, cg_records, did, norm, ordered, sentinels
from resonance_world.historical_substrate import bounded_historical_evidence

MODEL = "glm-5-turbo"
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
TEMPERATURE = 0.8
MAX_TOKENS = 96
MAX_ATTEMPTS = 4
CONCURRENCY = 6


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def flat_window(
    source: list[dict[str, Any]],
    unit: dict[str, Any],
    generation: str,
) -> list[dict[str, Any]]:
    cutoff = int(unit["decision_cutoffs"][generation])
    rows = ordered([row for row in source if int(row["observed_at"]) <= cutoff])
    return rows[-int(unit["result_limit"]):]


def family_rule(family: str) -> str:
    if family == "temporal_latest":
        return (
            "Use only predecessor_lesson records matching the CURRENT organization_id and predicate. "
            "Among admissible DIRECT records, find the newest observed_at. Its payload.decision_token "
            "FIRST means choose the lexicographically first offered action; SECOND means choose the "
            "lexicographically second offered action. If no such admissible direct lesson exists, "
            "the evidence is insufficient."
        )
    if family == "two_key_composition":
        return (
            "Use only predecessor_lesson records matching the CURRENT organization_id and predicate. "
            "Exactly two prior-generation direct lessons are required. Order them by observed_at and "
            "read payload.key_part from each. XOR the two integer bits. XOR 0 means choose the "
            "lexicographically first offered action; XOR 1 means choose the lexicographically second. "
            "With fewer than two admissible lessons, the evidence is insufficient."
        )
    if family == "provenance_temporal":
        return (
            "Use only predecessor_lesson records matching the CURRENT organization_id and predicate. "
            "Exactly one older SECONDARY/non-direct lesson and one newer DIRECT lesson are required. "
            "Read payload.signal from both. If the two bits are equal choose the lexicographically first "
            "offered action; if they differ choose the lexicographically second. With the required pair "
            "absent, the evidence is insufficient."
        )
    raise ValueError(family)


def scientific_prompt(
    *,
    unit: dict[str, Any],
    generation: str,
    replicate: str,
    member_id: str,
    rows: list[dict[str, Any]],
) -> str:
    actions = sorted(str(action) for action in unit["actions"])
    visible_rows = [
        {
            "record_id": row["record_id"],
            "organization_id": row["organization_id"],
            "predicate": row["predicate"],
            "observed_at": row["observed_at"],
            "source_class": row["source_class"],
            "direct": row["direct"],
            "record_kind": row["record_kind"],
            "payload": row["payload"],
        }
        for row in rows
    ]
    return "\n".join(
        [
            "You are a newly assigned successor member. You have no predecessor memory except the evidence below.",
            f"replicate={replicate} generation={generation} member_id={member_id}",
            f"CURRENT organization_id={unit['organization_id']} predicate={unit['predicate']}",
            f"OFFERED actions={json.dumps(actions, separators=(',', ':'))}",
            f"DECISION RULE: {family_rule(str(unit['family']))}",
            "History may contain irrelevant records from other scopes. Never treat mismatched organization_id or predicate as admissible.",
            "Do not infer an answer from opaque action names. If evidence is insufficient, make a best-effort choice between the offered actions and use an empty evidence_ids list.",
            "If evidence is sufficient, evidence_ids should contain only the record IDs you actually used, in chronological order.",
            "DELIVERED HISTORY:",
            json.dumps(visible_rows, sort_keys=True, separators=(",", ":")),
        ]
    )


def history_rows(
    *,
    source: list[dict[str, Any]],
    static_claims: list[dict[str, Any]],
    accumulating_claims: list[dict[str, Any]],
    unit: dict[str, Any],
    generation: str,
    arm: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request = {
        "query_id": unit["query_ids"][generation],
        "requesting_organization_id": unit["organization_id"],
        "predicate": unit["predicate"],
        "decision_cutoff": unit["decision_cutoffs"][generation],
        "result_limit": unit["result_limit"],
        "evidence_release_commit": CG,
    }
    if arm == "no_history":
        denial = bounded_historical_evidence(
            accumulating_claims,
            enabled=False,
            **request,
        )
        return [], {"kind": arm, "query_denial": denial}
    if arm == "flat_accumulating_history":
        rows = flat_window(source, unit, generation)
        return rows, {"kind": arm, "record_ids": [row["record_id"] for row in rows]}
    claims = static_claims if arm == "structured_static_history" else accumulating_claims
    if arm not in {
        "structured_static_history",
        "structured_accumulating_history",
    }:
        raise ValueError(f"unknown arm {arm}")
    bundle = bounded_historical_evidence(claims, enabled=True, **request)
    rows = norm(list(bundle["evidence"]))
    return rows, {
        "kind": arm,
        "bundle_id": bundle["bundle_id"],
        "record_ids": [row["record_id"] for row in rows],
    }


def prepare(evidence: dict[str, Any]) -> dict[str, Any]:
    source = ordered([dict(row) for row in evidence["evidence_records"]])
    legacy = ordered([dict(row) for row in evidence["legacy_records"]])
    accumulating_claims = cg_records(source)
    static_claims = cg_records(legacy)
    if norm(accumulating_claims) != source:
        raise ValueError("ContextGraph accumulating corpus differs from canonical source")
    if norm(static_claims) != legacy:
        raise ValueError("ContextGraph static corpus differs from legacy source")

    cells: list[dict[str, Any]] = []
    for replicate in evidence["replicates"]:
        for generation in evidence["generations"]:
            for arm in evidence["history_arms"]:
                for raw_unit in evidence["units"]:
                    unit = dict(raw_unit)
                    rows, history_meta = history_rows(
                        source=source,
                        static_claims=static_claims,
                        accumulating_claims=accumulating_claims,
                        unit=unit,
                        generation=generation,
                        arm=arm,
                    )
                    member_id = str(unit["members"][replicate][generation])
                    prompt = scientific_prompt(
                        unit=unit,
                        generation=generation,
                        replicate=replicate,
                        member_id=member_id,
                        rows=rows,
                    )
                    logical_id = did(
                        "h4-cell-",
                        {
                            "replicate": replicate,
                            "generation": generation,
                            "arm": arm,
                            "unit_id": unit["unit_id"],
                        },
                    )
                    cells.append(
                        {
                            "logical_cell_id": logical_id,
                            "unit_id": unit["unit_id"],
                            "family": unit["family"],
                            "replicate": replicate,
                            "generation": generation,
                            "history_arm": arm,
                            "member_id": member_id,
                            "organization_id": unit["organization_id"],
                            "predicate": unit["predicate"],
                            "actions": sorted(unit["actions"]),
                            "decision_cutoff": unit["decision_cutoffs"][generation],
                            "delivered_records": rows,
                            "delivered_record_ids": [row["record_id"] for row in rows],
                            "history_meta": history_meta,
                            "prompt": prompt,
                            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                        }
                    )
    return {
        "schema": "h4-request-plan-v0.1",
        "world_preregistered_base": evidence["world_preregistered_base"],
        "contextgraph_release_commit": CG,
        "model_contract": evidence["model_contract"],
        "canonical_corpus_sha256": hashlib.sha256(cb(source)).hexdigest(),
        "legacy_corpus_sha256": hashlib.sha256(cb(legacy)).hexdigest(),
        "cells": cells,
        "direct_edge_sentinels": sentinels(),
        "production_historical_substrate_enabled": False,
    }


class ZAIClient:
    def __init__(self, api_key: str) -> None:
        if not api_key.strip():
            raise ValueError("empty ZAI_API_KEY")
        self.api_key = api_key
        self._random = random.Random(470401)
        self._lock = threading.Lock()

    def _request_id(self, logical_id: str, attempt: int) -> str:
        with self._lock:
            nonce = self._random.getrandbits(64)
        return f"h4-{logical_id[-12:]}-{attempt}-{nonce:016x}"

    def complete(self, cell: dict[str, Any]) -> dict[str, Any]:
        system = (
            "Return exactly one JSON object with keys action and evidence_ids. action must be one of "
            f"{', '.join(cell['actions'])}. evidence_ids must be a JSON array of zero or more strings. "
            "Do not add any other keys or text outside the JSON object."
        )
        attempt_log: list[dict[str, Any]] = []
        started_all = time.perf_counter()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request_id = self._request_id(str(cell["logical_cell_id"]), attempt)
            body = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": cell["prompt"]},
                ],
                "thinking": {"type": "disabled"},
                "do_sample": True,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "stream": False,
                "response_format": {"type": "json_object"},
                "request_id": request_id,
            }
            request_bytes = json.dumps(body, separators=(",", ":")).encode()
            request = Request(
                ENDPOINT,
                data=request_bytes,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept-Language": "en-US,en",
                    "User-Agent": "resonance-world-h4/0.1",
                },
                method="POST",
            )
            started = time.perf_counter()
            try:
                with urlopen(request, timeout=90.0) as response:
                    raw = response.read()
                latency_ms = (time.perf_counter() - started) * 1000.0
                outer = json.loads(raw.decode())
                if outer.get("model") != MODEL:
                    raise ValueError(f"model drift: {outer.get('model')!r}")
                choices = outer.get("choices")
                if not isinstance(choices, list) or len(choices) != 1:
                    raise ValueError("expected exactly one choice")
                content = choices[0].get("message", {}).get("content")
                payload = json.loads(content)
                if not isinstance(payload, dict) or set(payload) != {
                    "action",
                    "evidence_ids",
                }:
                    raise ValueError("invalid output keys")
                if payload["action"] not in cell["actions"]:
                    raise ValueError("action outside offered vocabulary")
                if not isinstance(payload["evidence_ids"], list) or not all(
                    isinstance(item, str) for item in payload["evidence_ids"]
                ):
                    raise ValueError("evidence_ids must be string list")
                usage = outer.get("usage", {})
                attempt_log.append(
                    {
                        "attempt": attempt,
                        "request_id": request_id,
                        "status": "ok",
                        "latency_ms": round(latency_ms, 3),
                    }
                )
                return {
                    "logical_cell_id": cell["logical_cell_id"],
                    "model": MODEL,
                    "action": payload["action"],
                    "evidence_ids": payload["evidence_ids"],
                    "input_tokens": int(usage.get("prompt_tokens", 0)),
                    "output_tokens": int(usage.get("completion_tokens", 0)),
                    "attempt_log": attempt_log,
                    "total_latency_ms": round(
                        (time.perf_counter() - started_all) * 1000.0,
                        3,
                    ),
                }
            except HTTPError as exc:
                latency_ms = (time.perf_counter() - started) * 1000.0
                retryable = exc.code == 429 or exc.code >= 500
                attempt_log.append(
                    {
                        "attempt": attempt,
                        "request_id": request_id,
                        "status": f"http_{exc.code}",
                        "latency_ms": round(latency_ms, 3),
                    }
                )
                if not retryable or attempt == MAX_ATTEMPTS:
                    detail = exc.read().decode(errors="replace")[:1000]
                    raise RuntimeError(f"Z.AI HTTP {exc.code}: {detail}") from exc
            except (
                URLError,
                TimeoutError,
                json.JSONDecodeError,
                ValueError,
            ) as exc:
                latency_ms = (time.perf_counter() - started) * 1000.0
                attempt_log.append(
                    {
                        "attempt": attempt,
                        "request_id": request_id,
                        "status": type(exc).__name__,
                        "latency_ms": round(latency_ms, 3),
                    }
                )
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError(
                        f"Z.AI request failed after {attempt} attempts: {exc}"
                    ) from exc
            time.sleep(min(8.0, 2.0 ** (attempt - 1)))
        raise AssertionError("unreachable")


def execute(plan: dict[str, Any], api_key: str) -> dict[str, Any]:
    client = ZAIClient(api_key)
    responses: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        future_to_cell = {
            pool.submit(client.complete, cell): cell for cell in plan["cells"]
        }
        for future in as_completed(future_to_cell):
            cell = future_to_cell[future]
            response = future.result()
            responses[str(cell["logical_cell_id"])] = response
            print(
                f"H4_PROGRESS {len(responses)}/{len(plan['cells'])} "
                f"{cell['replicate']} {cell['generation']} "
                f"{cell['history_arm']} {cell['unit_id']}",
                flush=True,
            )
    cells = []
    for cell in plan["cells"]:
        public_cell = {key: value for key, value in cell.items() if key != "prompt"}
        public_cell["model_response"] = responses[str(cell["logical_cell_id"])]
        cells.append(public_cell)
    return {
        "schema": "h4-live-output-v0.1",
        "world_preregistered_base": plan["world_preregistered_base"],
        "contextgraph_release_commit": plan["contextgraph_release_commit"],
        "model_contract": plan["model_contract"],
        "canonical_corpus_sha256": plan["canonical_corpus_sha256"],
        "legacy_corpus_sha256": plan["legacy_corpus_sha256"],
        "logical_cell_count": len(cells),
        "cells": cells,
        "direct_edge_sentinels": plan["direct_edge_sentinels"],
        "production_historical_substrate_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--api-key-env", default="ZAI_API_KEY")
    args = parser.parse_args()
    evidence = load(args.plane_e)
    plan = prepare(evidence)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "h4-request-plan.json").write_bytes(cb(plan))
    if args.prepare_only:
        return 0
    api_key = os.environ.get(args.api_key_env, "")
    live = execute(plan, api_key)
    live_bytes = cb(live)
    (args.output_dir / "h4-live-output.json").write_bytes(live_bytes)
    print("H4_LIVE_SHA256=" + hashlib.sha256(live_bytes).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
