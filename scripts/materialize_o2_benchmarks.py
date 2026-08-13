#!/usr/bin/env python3
"""Materialize the preregistered O2 aggregate-collision benchmark corpus.

This script implements only the pre-outcome apparatus defined in issue #122.
It does not ingest ContextGraph evidence, answer O2 researcher queries, or
evaluate O2 acceptance gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "o2-benchmark-v0.1"
BASE_REVISION = "28796c01c26a93e718da7de2ab01185cb2982cbd"
RELABELINGS = 4
TEMPLATES = ("C1", "C2", "D1", "D2", "T1", "T2", "R1", "R2", "S1", "S2")
NEGATIVE_CONTROLS = (
    "latent_private_field_capability",
    "counterfactual_member_necessity",
    "hidden_constructor_template_regime",
    "evaluator_variant_identity",
    "private_relationship_store_state",
    "hidden_w9_source_frontier_state",
    "future_unobserved_outcome",
    "provenance_implies_causal_benefit",
)
NOT_IDENTIFIABLE = "not_observationally_identifiable"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def opaque(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return "o2-" + hashlib.sha256(("resonance-o2-v1|" + payload).encode()).hexdigest()[:24]


def relabel(template: str, relabel_index: int) -> dict[str, str]:
    semantic = ["org", "m0", "m1", "m2", "m3", "m4", "m5", "source", "relation0", "role0"]
    return {token: opaque("entity", template, relabel_index, token) for token in semantic}


def event(
    template: str,
    relabel_index: int,
    variant: str,
    seq: int,
    kind: str,
    interval: int,
    *,
    entities: dict[str, str],
    subject: str | None = None,
    object_: str | None = None,
    attempts: int | None = None,
    successes: int | None = None,
    members: Iterable[str] | None = None,
    departing: str | None = None,
    arriving: str | None = None,
    public_resource: int | None = None,
    active: bool | None = None,
    provenance_tokens: Iterable[str] | None = None,
) -> dict[str, Any]:
    event_id = opaque("event", template, relabel_index, variant, seq)
    row: dict[str, Any] = {
        "event_id": event_id,
        "ordinal": seq,
        "interval": interval,
        "kind": kind,
        "organization_id": entities["org"],
    }
    if subject is not None:
        row["subject_id"] = entities[subject]
    if object_ is not None:
        row["object_id"] = entities[object_]
    if attempts is not None:
        row["attempts"] = attempts
    if successes is not None:
        row["successes"] = successes
    if members is not None:
        row["member_ids"] = sorted(entities[token] for token in members)
    if departing is not None:
        row["departing_member_id"] = entities[departing]
    if arriving is not None:
        row["arriving_member_id"] = entities[arriving]
    if public_resource is not None:
        row["public_resource"] = public_resource
    if active is not None:
        row["active"] = active
    if provenance_tokens is not None:
        row["provenance_event_ids"] = [
            opaque("event", template, relabel_index, variant, int(token))
            for token in provenance_tokens
        ]
    return row


def performance_series(template: str, ri: int, variant: str, entities: dict[str, str], carriers: list[str], successes: list[int], *, start_seq: int = 1) -> list[dict[str, Any]]:
    assert len(carriers) == len(successes)
    rows = []
    for offset, (carrier, success) in enumerate(zip(carriers, successes, strict=True)):
        rows.append(event(template, ri, variant, start_seq + offset, "performance", offset + 1, entities=entities, subject=carrier, attempts=1, successes=success))
    return rows


def template_c1(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    success = [0, 1, 1, 0, 1, 1] if variant == "a" else [0, 0, 1, 1, 1, 1]
    events = [event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1", "m2"))]
    events.extend(performance_series(template, ri, variant, e, ["m0"] * 6, success, start_seq=2))
    first_success = next(i + 1 for i, x in enumerate(success) if x)
    return events, {"first_success_interval": first_success, "success_count_trajectory": success}


def template_c2(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if variant == "a":
        carriers = ["m0", "m1", "m2", "m0", "m3", "m0"]
    else:
        carriers = ["m0", "m0", "m0", "m1", "m3", "m2"]
    success = [1, 1, 1, 0, 1, 0]
    events = [event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1", "m2", "m3"))]
    events.extend(performance_series(template, ri, variant, e, carriers, success, start_seq=2))
    per_member = {e[f"m{i}"]: [0] * 6 for i in range(4)}
    seen: set[str] = set()
    carrier_sets: list[list[str]] = []
    first_multi = None
    for idx, (carrier, ok) in enumerate(zip(carriers, success, strict=True)):
        if ok:
            per_member[e[carrier]][idx] += 1
            seen.add(e[carrier])
        carrier_sets.append(sorted(seen))
        if first_multi is None and len(seen) > 1:
            first_multi = idx + 1
    return events, {
        "per_member_success_trajectory": per_member,
        "first_multi_carrier_interval": first_multi,
        "carrier_set_by_interval": carrier_sets,
    }


def template_d1(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if variant == "a":
        carriers = ["m0", "m0", "m0", "m3", "m1", "m3"]
        success = [1, 1, 1, 0, 0, 1]
    else:
        carriers = ["m0", "m1", "m2", "m3", "m1", "m2"]
        success = [1, 1, 1, 1, 0, 0]
    events = [event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1", "m2"))]
    for idx in range(3):
        events.append(event(template, ri, variant, 2 + idx, "performance", idx + 1, entities=e, subject=carriers[idx], attempts=1, successes=success[idx]))
    events.append(event(template, ri, variant, 5, "turnover", 4, entities=e, departing="m0", arriving="m3", members=("m1", "m2", "m3")))
    for idx in range(3, 6):
        events.append(event(template, ri, variant, 3 + idx, "performance", idx + 1, entities=e, subject=carriers[idx], attempts=1, successes=success[idx]))
    post = success[3:]
    recovery = next((idx + 4 for idx, x in enumerate(post) if x), None)
    return events, {
        "departing_carrier_id": e["m0"],
        "pre_departure_success_counts": success[:3],
        "post_departure_success_counts": post,
        "recovery_interval": recovery,
    }


def template_d2(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if variant == "a":
        carriers = ["m0", "m0", "m0", "m0", "m1", "m2"]
    else:
        carriers = ["m0", "m0", "m1", "m2", "m3", "m3"]
    success = [1, 1, 1, 1, 0, 0]
    events = [event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1", "m2", "m3"))]
    events.extend(performance_series(template, ri, variant, e, carriers, success, start_seq=2))
    counts = Counter(e[c] for c, ok in zip(carriers, success, strict=True) if ok)
    vector = {member: counts.get(member, 0) for member in sorted(e[f"m{i}"] for i in range(4))}
    maximum = max(vector.values())
    max_members = sorted(member for member, count in vector.items() if count == maximum)
    return events, {
        "contribution_vector": vector,
        "maximum_contributing_members": max_members,
        "maximum_contribution_share": {"numerator": maximum, "denominator": sum(vector.values())},
    }


def template_t1(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    success = [1, 1, 1, 1, 0, 0] if variant == "a" else [1, 1, 0, 0, 1, 1]
    carriers = ["m0", "m1", "m2", "m3", "m2", "m3"]
    events = [
        event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1")),
        event(template, ri, variant, 2, "performance", 1, entities=e, subject=carriers[0], attempts=1, successes=success[0]),
        event(template, ri, variant, 3, "performance", 2, entities=e, subject=carriers[1], attempts=1, successes=success[1]),
        event(template, ri, variant, 4, "generation_transition", 3, entities=e, members=("m2", "m3")),
    ]
    for idx in range(2, 6):
        events.append(event(template, ri, variant, 3 + idx, "performance", idx + 1, entities=e, subject=carriers[idx], attempts=1, successes=success[idx]))
    post = success[2:]
    recovered = next((idx + 3 for idx, x in enumerate(post) if x), None)
    return events, {
        "generation_transition_interval": 3,
        "post_turnover_success_trajectory": post,
        "first_recovered_interval": recovered,
    }


def template_t2(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = [
        event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1")),
        event(template, ri, variant, 2, "evidence", 1, entities=e, subject="m0"),
        event(template, ri, variant, 3, "generation_transition", 3, entities=e, members=("m2", "m3")),
        event(template, ri, variant, 4, "evidence", 4, entities=e, subject="m2"),
        event(template, ri, variant, 5, "evidence", 5, entities=e, subject="m3"),
    ]
    provenance = ("2", "4", "5") if variant == "a" else ("4", "5")
    events.append(event(template, ri, variant, 6, "decision", 6, entities=e, subject="m2", object_="role0", provenance_tokens=provenance))
    events.append(event(template, ri, variant, 7, "performance", 6, entities=e, subject="m2", attempts=1, successes=1))
    chain = [opaque("event", template, ri, variant, int(x)) for x in provenance]
    return events, {
        "decision_provenance_chain": chain,
        "provenance_crosses_generation_boundary": variant == "a",
    }


def template_r1(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pairs = [("m0", "m1")] * 6 if variant == "a" else [("m0", "m1"), ("m0", "m2"), ("m1", "m2"), ("m0", "m1"), ("m0", "m2"), ("m1", "m2")]
    success = [1, 1, 0, 1, 1, 0]
    events = [event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1", "m2"))]
    per_pair: dict[str, list[dict[str, int]]] = defaultdict(list)
    for idx, ((left, right), ok) in enumerate(zip(pairs, success, strict=True), start=1):
        pair_entity = opaque("pair-entity", template, ri, *sorted((left, right)))
        row = event(template, ri, variant, idx + 1, "interaction", idx, entities=e, subject=left, object_=right, attempts=1, successes=ok)
        row["relationship_id"] = pair_entity
        events.append(row)
        per_pair[pair_entity].append({"interval": idx, "successes": ok})
    return events, {
        "pair_interaction_intervals": {pair: rows for pair, rows in sorted(per_pair.items())},
        "pair_ids": sorted(per_pair),
    }


def template_r2(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    relation = opaque("pair-entity", template, ri, "m0", "m1")
    events = [event(template, ri, variant, 1, "membership", 0, entities=e, members=("m0", "m1"))]
    start = event(template, ri, variant, 2, "relation_state", 1, entities=e, subject="m0", object_="m1", active=True)
    start["relationship_id"] = relation
    events.append(start)
    seq = 3
    rupture_event_id = None
    reformation_event_id = None
    if variant == "b":
        rupture = event(template, ri, variant, seq, "relation_state", 3, entities=e, subject="m0", object_="m1", active=False)
        rupture["relationship_id"] = relation
        rupture_event_id = rupture["event_id"]
        events.append(rupture)
        seq += 1
        reform = event(template, ri, variant, seq, "relation_state", 5, entities=e, subject="m0", object_="m1", active=True)
        reform["relationship_id"] = relation
        reformation_event_id = reform["event_id"]
        events.append(reform)
        seq += 1
    for interval, ok in [(1, 1), (2, 1), (5, 1), (6, 0)]:
        row = event(template, ri, variant, seq, "interaction", interval, entities=e, subject="m0", object_="m1", attempts=1, successes=ok)
        row["relationship_id"] = relation
        events.append(row)
        seq += 1
    return events, {
        "relation_active_intervals": [1, 2, 3, 4, 5, 6] if variant == "a" else [1, 2, 5, 6],
        "rupture_event_id": rupture_event_id,
        "reformation_event_id": reformation_event_id,
    }


def template_s1(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resource = [100, 100, 100, 100, 100, 100] if variant == "a" else [100, 90, 80, 90, 100, 100]
    success = [1, 1, 0, 1, 1, 0] if variant == "a" else [1, 0, 0, 1, 1, 1]
    events = []
    seq = 1
    for idx in range(6):
        events.append(event(template, ri, variant, seq, "source_public_state", idx + 1, entities=e, subject="source", public_resource=resource[idx]))
        seq += 1
        events.append(event(template, ri, variant, seq, "service", idx + 1, entities=e, subject="source", object_="org", attempts=1, successes=success[idx]))
        seq += 1
    first_negative = None
    recovery = None
    for idx in range(1, len(resource)):
        if first_negative is None and resource[idx] < resource[idx - 1]:
            first_negative = idx + 1
        if first_negative is not None and recovery is None and resource[idx] >= resource[0]:
            recovery = idx + 1
    return events, {
        "first_negative_public_trajectory_interval": first_negative,
        "recovery_interval": recovery,
        "service_success_trajectory": success,
    }


def template_s2(template: str, ri: int, variant: str, e: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    success = [0, 1, 0, 1, 1, 1] if variant == "a" else [1, 1, 1, 1, 0, 0]
    events = []
    seq = 1
    for idx, ok in enumerate(success, start=1):
        events.append(event(template, ri, variant, seq, "source_public_state", idx, entities=e, subject="source", public_resource=100))
        seq += 1
        events.append(event(template, ri, variant, seq, "service", idx, entities=e, subject="source", object_="org", attempts=1, successes=ok))
        seq += 1
    failures = [idx + 1 for idx, ok in enumerate(success) if not ok]
    prefix = []
    running = 0
    for ok in success:
        running += int(not ok)
        prefix.append(running)
    return events, {"failure_intervals": failures, "prefix_cumulative_failures": prefix}


BUILDERS = {
    "C1": template_c1,
    "C2": template_c2,
    "D1": template_d1,
    "D2": template_d2,
    "T1": template_t1,
    "T2": template_t2,
    "R1": template_r1,
    "R2": template_r2,
    "S1": template_s1,
    "S2": template_s2,
}

QUERY_MANIFEST = {
    "C1": [{"query_id": "first_success_interval", "kind": "identifiable"}, {"query_id": "success_count_trajectory", "kind": "identifiable"}],
    "C2": [{"query_id": "per_member_success_trajectory", "kind": "identifiable"}, {"query_id": "first_multi_carrier_interval", "kind": "identifiable"}, {"query_id": "carrier_set_by_interval", "kind": "identifiable"}],
    "D1": [{"query_id": "departing_carrier_id", "kind": "identifiable"}, {"query_id": "pre_departure_success_counts", "kind": "identifiable"}, {"query_id": "post_departure_success_counts", "kind": "identifiable"}, {"query_id": "recovery_interval", "kind": "identifiable"}],
    "D2": [{"query_id": "contribution_vector", "kind": "identifiable"}, {"query_id": "maximum_contributing_members", "kind": "identifiable"}, {"query_id": "maximum_contribution_share", "kind": "identifiable"}],
    "T1": [{"query_id": "generation_transition_interval", "kind": "identifiable"}, {"query_id": "post_turnover_success_trajectory", "kind": "identifiable"}, {"query_id": "first_recovered_interval", "kind": "identifiable"}],
    "T2": [{"query_id": "decision_provenance_chain", "kind": "identifiable"}, {"query_id": "provenance_crosses_generation_boundary", "kind": "identifiable"}],
    "R1": [{"query_id": "pair_interaction_intervals", "kind": "identifiable"}, {"query_id": "pair_ids", "kind": "identifiable"}],
    "R2": [{"query_id": "relation_active_intervals", "kind": "identifiable"}, {"query_id": "rupture_event_id", "kind": "identifiable"}, {"query_id": "reformation_event_id", "kind": "identifiable"}],
    "S1": [{"query_id": "first_negative_public_trajectory_interval", "kind": "identifiable"}, {"query_id": "recovery_interval", "kind": "identifiable"}, {"query_id": "service_success_trajectory", "kind": "identifiable"}],
    "S2": [{"query_id": "failure_intervals", "kind": "identifiable"}, {"query_id": "prefix_cumulative_failures", "kind": "identifiable"}],
}


def endpoint_aggregate(events: list[dict[str, Any]], pair_id: str) -> dict[str, Any]:
    total_attempts = sum(row.get("attempts", 0) for row in events if row["kind"] == "performance")
    total_successes = sum(row.get("successes", 0) for row in events if row["kind"] == "performance")
    service_attempts = sum(row.get("attempts", 0) for row in events if row["kind"] == "service")
    service_successes = sum(row.get("successes", 0) for row in events if row["kind"] == "service")
    interactions = [row for row in events if row["kind"] == "interaction"]
    relationship_successes = sum(row.get("successes", 0) for row in interactions)
    transition_rows = [row for row in events if row["kind"] in {"turnover", "generation_transition"}]
    member_rows = [row for row in events if "member_ids" in row]
    final_members = member_rows[-1]["member_ids"] if member_rows else []
    relation_states: dict[str, bool] = {}
    for row in events:
        if row["kind"] == "relation_state":
            relation_states[row["relationship_id"]] = bool(row["active"])
    public_states = [row["public_resource"] for row in events if row["kind"] == "source_public_state"]
    return {
        "schema": "o2-r0-endpoint-v0.1",
        "pair_id": pair_id,
        "final_interval": max(row["interval"] for row in events),
        "final_members": final_members,
        "turnover_total": len(transition_rows),
        "performance_attempts": total_attempts,
        "performance_successes": total_successes,
        "relationship_interactions": len(interactions),
        "relationship_successes": relationship_successes,
        "final_active_relationship_count": sum(relation_states.values()),
        "service_attempts": service_attempts,
        "service_successes": service_successes,
        "final_public_resource": public_states[-1] if public_states else None,
    }


def validate_events(events: list[dict[str, Any]]) -> None:
    ordinals = [row["ordinal"] for row in events]
    if len(ordinals) != len(set(ordinals)):
        raise ValueError("duplicate event ordinal")
    if ordinals != sorted(ordinals):
        raise ValueError("events are not in canonical ordinal order")
    ids = [row["event_id"] for row in events]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate event id")


def file_manifest(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes()) for path in sorted(p for p in root.rglob("*") if p.is_file())}


def manifest_root(rows: dict[str, str]) -> str:
    payload = "".join(f"{path}\0{digest}\n" for path, digest in sorted(rows.items())).encode()
    return sha256_bytes(payload)


def materialize(output_root: Path) -> dict[str, Any]:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    plane_e = output_root / "plane_e"
    plane_k = output_root / "plane_k"
    r0_dir = output_root / "r0"
    r1_dir = output_root / "r1"
    meta_dir = output_root / "meta"

    query_manifest = {
        "schema": "o2-query-manifest-v0.1",
        "templates": QUERY_MANIFEST,
        "negative_controls": [{"query_id": query_id, "expected": NOT_IDENTIFIABLE} for query_id in NEGATIVE_CONTROLS],
    }
    write_json(meta_dir / "query-manifest.json", query_manifest)

    relabel_records = []
    template_records = []
    collision_records = []
    for template in TEMPLATES:
        template_records.append({
            "template": template,
            "semantic_family": template[0],
            "relabelings": RELABELINGS,
            "variants": 2,
            "query_ids": [row["query_id"] for row in QUERY_MANIFEST[template]],
        })
        for ri in range(RELABELINGS):
            entities = relabel(template, ri)
            pair_id = opaque("collision-pair", template, ri)
            relabel_records.append({
                "template": template,
                "relabel_index": ri,
                "opaque_entity_ids": sorted(entities.values()),
                "pair_id": pair_id,
            })
            r0_payloads: dict[str, bytes] = {}
            answers_by_variant: dict[str, dict[str, Any]] = {}
            for variant in ("a", "b"):
                history_id = opaque("history", template, ri, variant)
                events, answers = BUILDERS[template](template, ri, variant, entities)
                validate_events(events)
                e_doc = {"schema": "o2-plane-e-history-v0.1", "history_id": history_id, "pair_id": pair_id, "events": events}
                k_doc = {
                    "schema": "o2-plane-k-history-v0.1",
                    "history_id": history_id,
                    "pair_id": pair_id,
                    "template": template,
                    "variant": variant,
                    "distinguishing_answers": answers,
                    "negative_controls": {query_id: NOT_IDENTIFIABLE for query_id in NEGATIVE_CONTROLS},
                }
                r0 = endpoint_aggregate(events, pair_id)
                r1 = {"schema": "o2-r1-flat-log-v0.1", "history_id": history_id, "pair_id": pair_id, "events": events}
                filename = f"{pair_id}--{history_id}.json"
                write_json(plane_e / filename, e_doc)
                write_json(plane_k / filename, k_doc)
                write_json(r1_dir / filename, r1)
                write_json(r0_dir / f"{pair_id}--{variant}.json", r0)
                r0_payloads[variant] = canonical_bytes(r0)
                answers_by_variant[variant] = answers
            if r0_payloads["a"] != r0_payloads["b"]:
                raise ValueError(f"aggregate collision failed for {template}/{ri}")
            if canonical_bytes(answers_by_variant["a"]) == canonical_bytes(answers_by_variant["b"]):
                raise ValueError(f"distinguishing answer collision for {template}/{ri}")
            collision_records.append({
                "template": template,
                "relabel_index": ri,
                "pair_id": pair_id,
                "r0_sha256": sha256_bytes(r0_payloads["a"]),
                "answers_differ": True,
            })

    write_json(meta_dir / "template-manifest.json", {
        "schema": "o2-template-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "templates": template_records,
        "semantic_template_count": len(TEMPLATES),
        "relabelings_per_template": RELABELINGS,
        "collision_pairs": len(TEMPLATES) * RELABELINGS,
        "histories": len(TEMPLATES) * RELABELINGS * 2,
    })
    write_json(meta_dir / "relabeling-manifest.json", {"schema": "o2-relabeling-manifest-v0.1", "records": relabel_records})
    write_json(meta_dir / "collision-manifest.json", {"schema": "o2-collision-manifest-v0.1", "records": collision_records})

    roots = {}
    for name, directory in (("plane_e", plane_e), ("plane_k", plane_k), ("r0", r0_dir), ("r1", r1_dir), ("meta", meta_dir)):
        rows = file_manifest(directory)
        roots[name] = {"file_count": len(rows), "manifest_root_sha256": manifest_root(rows), "files": rows}

    lock = {
        "schema": "o2-apparatus-materialization-v0.1",
        "base_revision": BASE_REVISION,
        "generator_schema": SCHEMA_VERSION,
        "semantic_template_count": len(TEMPLATES),
        "relabelings_per_template": RELABELINGS,
        "collision_pair_count": len(TEMPLATES) * RELABELINGS,
        "history_count": len(TEMPLATES) * RELABELINGS * 2,
        "roots": roots,
    }
    write_json(output_root / "materialization-manifest.json", lock)
    return lock


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    lock = materialize(args.output_root)
    print(json.dumps(lock, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
