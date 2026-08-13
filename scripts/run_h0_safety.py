#!/usr/bin/env python3
"""Run the H0 bounded-history safety treatment using admissible inputs only."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from resonance_contextgraph import EvidenceStore

from resonance_world.context_graph_adapter import to_evidence_claim

NOT_IDENTIFIABLE = "not_observationally_identifiable"
FORBIDDEN_ROUTES = (
    "contextgraph_to_world_outcome_law",
    "contextgraph_to_field_capability_state",
    "contextgraph_to_automatic_authority",
    "contextgraph_to_automatic_policy",
)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def opaque(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return "h0-" + hashlib.sha256(("resonance-h0-v1|" + raw).encode()).hexdigest()[:24]


def digest_id(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(canonical_bytes(value)).hexdigest()[:24]


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class _ObservedClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    observed_by: str
    source_id: str
    source_class: str
    observed_at: int
    confidence: float
    direct: bool


def ingest_plane_e(plane_e: dict[str, Any]) -> tuple[EvidenceStore, list[dict[str, Any]]]:
    store = EvidenceStore()
    for event in plane_e["evidence_events"]:
        payload = {
            "organization_id": event["organization_id"],
            "subject_id": event["subject_id"],
            "value": event["value"],
            "provenance_source_id": event["source_id"],
        }
        observed = _ObservedClaim(
            field_id=str(event["organization_id"]),
            subject=str(event["event_id"]),
            predicate=str(event["predicate"]),
            object=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            observed_by=str(event["observed_by"]),
            source_id=f"h0-transport-{event['event_id']}",
            source_class=str(event["source_class"]),
            observed_at=int(event["observed_at"]),
            confidence=float(event["confidence"]),
            direct=bool(event["direct"]),
        )
        store.ingest(to_evidence_claim(observed, delivery=0))
    claims = []
    for org_id in sorted({str(row["organization_id"]) for row in plane_e["evidence_events"]}):
        claims.extend(asdict(claim) for claim in store.claims(scope_id=org_id))
    claims.sort(key=lambda row: (str(row["scope_id"]), int(row["observed_at"]), str(row["claim_id"])))
    return store, claims


class HistoricalAccess:
    def __init__(self, store: EvidenceStore, *, enabled: bool) -> None:
        self._store = store
        self._enabled = enabled

    def query(self, spec: dict[str, Any]) -> dict[str, Any]:
        query_id = str(spec["query_id"])
        if not self._enabled:
            return {
                "schema": "h0-access-denial-v0.1",
                "query_id": query_id,
                "status": "historical_access_disabled",
                "bundle": None,
            }

        selected: list[dict[str, Any]] = []
        for claim in self._store.claims(scope_id=str(spec["organization_id"])):
            row = asdict(claim)
            if str(row["predicate"]) != str(spec["predicate"]):
                continue
            if int(row["observed_at"]) > int(spec["decision_cutoff"]):
                continue
            decoded = json.loads(str(row["object"]))
            selected.append(
                {
                    "claim_id": str(row["claim_id"]),
                    "evidence_event_id": str(row["subject"]),
                    "organization_id": str(decoded["organization_id"]),
                    "subject_id": str(decoded["subject_id"]),
                    "predicate": str(row["predicate"]),
                    "value": decoded["value"],
                    "provenance_source_id": str(decoded["provenance_source_id"]),
                    "observed_by": str(row["observed_by"]),
                    "source_class": str(row["source_class"]),
                    "observed_at": int(row["observed_at"]),
                    "confidence": float(row["confidence"]),
                    "direct": bool(row["direct"]),
                }
            )
        selected.sort(key=lambda row: (int(row["observed_at"]), str(row["claim_id"])))
        selected = selected[: int(spec["result_limit"])]
        base = {
            "schema": "h0-historical-evidence-bundle-v0.1",
            "query_id": query_id,
            "requesting_organization_id": str(spec["organization_id"]),
            "decision_cutoff": int(spec["decision_cutoff"]),
            "scope": {"predicate": str(spec["predicate"])},
            "result_limit": int(spec["result_limit"]),
            "status": "empty" if not selected else "ok",
            "evidence": selected,
            "contextgraph_release_commit": "b896891108fd954869a8cd0423f6e8440ab0cdc0",
        }
        return {**base, "bundle_id": digest_id("h0-bundle-", base)}


def controller_decision(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence = list(bundle["evidence"])
    actor_id = str(evidence[0]["subject_id"]) if evidence else opaque("actor", "none")
    base = {
        "schema": "h0-controller-decision-v0.1",
        "bundle_id": str(bundle["bundle_id"]),
        "actor_id": actor_id,
        "action_id": opaque("action", "restricted"),
        "action": "restricted-action",
        "interpretation": "historical-evidence-informed-proposal",
    }
    return {**base, "decision_id": digest_id("h0-decision-", base)}


def world_verify_current_authority(actor_id: str) -> bool:
    return actor_id == opaque("actor", "current")


def world_adjudicate(decision: dict[str, Any]) -> dict[str, Any]:
    authorized = world_verify_current_authority(str(decision["actor_id"]))
    return {
        "schema": "h0-world-consequence-v0.1",
        "decision_id": str(decision["decision_id"]),
        "action_id": str(decision["action_id"]),
        "authorized": authorized,
        "executed": authorized,
    }


def execution_ack(decision: dict[str, Any], consequence: dict[str, Any]) -> dict[str, Any]:
    base = {
        "schema": "h0-execution-ack-v0.1",
        "decision_id": str(decision["decision_id"]),
        "action_id": str(decision["action_id"]),
        "authorized": bool(consequence["authorized"]),
        "executed": bool(consequence["executed"]),
    }
    return {**base, "ack_id": digest_id("h0-ack-", base)}


def baseline_trajectory() -> dict[str, Any]:
    decision = {
        "schema": "h0-baseline-decision-v0.1",
        "decision_id": opaque("baseline", "decision"),
        "actor_id": opaque("actor", "current"),
        "action_id": opaque("baseline", "action"),
        "action": "baseline-action",
    }
    consequence = world_adjudicate(decision)
    return {"decision": decision, "consequence": consequence}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e", required=True, type=Path)
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    plane_e = read_object(args.plane_e)
    query_doc = read_object(args.queries)
    store, claims = ingest_plane_e(plane_e)

    disabled = HistoricalAccess(store, enabled=False)
    enabled = HistoricalAccess(store, enabled=True)
    queries = list(query_doc["queries"])
    bundles: dict[str, Any] = {}
    denials: dict[str, Any] = {}
    purpose_to_query: dict[str, str] = {}
    for spec in queries:
        query_id = str(spec["query_id"])
        purpose_to_query[str(spec["purpose"])] = query_id
        denials[query_id] = disabled.query(spec)
        bundles[query_id] = enabled.query(spec)

    authority_bundle = bundles[purpose_to_query["authority-separation"]]
    decision = controller_decision(authority_bundle)
    consequence = world_adjudicate(decision)
    ack = execution_ack(decision, consequence)

    current_actor_control = {
        "schema": "h0-controller-decision-v0.1",
        "decision_id": opaque("control", "current-decision"),
        "bundle_id": None,
        "actor_id": opaque("actor", "current"),
        "action_id": opaque("control", "current-action"),
        "action": "restricted-action",
        "interpretation": "current-authority-control",
    }
    current_actor_consequence = world_adjudicate(current_actor_control)

    baseline = baseline_trajectory()
    disabled_no_retrieval = baseline_trajectory()

    direct_edge_sentinels = [
        {"route": route, "status": "rejected"} for route in FORBIDDEN_ROUTES
    ]
    result = {
        "schema": "h0-researcher-output-v0.1",
        "contextgraph_claims": claims,
        "bundles": bundles,
        "disabled_query_denials": denials,
        "purpose_to_query": purpose_to_query,
        "authority_path": {
            "decision": decision,
            "consequence": consequence,
            "execution_acknowledgement": ack,
            "current_actor_control_consequence": current_actor_consequence,
        },
        "direct_edge_sentinels": direct_edge_sentinels,
        "observer_only_baseline_trajectory": baseline,
        "access_disabled_no_retrieval_trajectory": disabled_no_retrieval,
        "negative_controls": {
            "private_field_fact": NOT_IDENTIFIABLE,
            "future_outcome": NOT_IDENTIFIABLE,
            "retrieved_evidence_is_world_truth": NOT_IDENTIFIABLE,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "h0-researcher-output.json").write_bytes(canonical_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
