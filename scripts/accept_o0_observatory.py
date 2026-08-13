#!/usr/bin/env python3
"""Evaluate the preregistered O0 Observatory non-interference gates."""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import resonance_world.w4a_joint_learning as joint_learning
from resonance_world.context_graph_runtime import HISTORICAL_SUBSTRATE_ENABLED
from resonance_world.observatory import (
    EVENT_TYPE,
    OBSERVER_ID,
    PREDICATES,
    SOURCE_CLASS,
    ContextGraphObservatory,
)
from resonance_world.w4a_joint_learning import JointController, JointEnvironment

FROZEN_WORLD_BASE = "2b618ae277d6b34028f91886ace7aad1839f11c9"
CONTEXTGRAPH_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
SEEDS = (7001, 7103, 7207, 7309, 7411)
CONDITIONS = ("communication-0", "communication-1")
LEAD_SKILL = "planning"
SUPPORT_SKILL = "verification"
EXPECTED_UNITS = len(SEEDS) * len(CONDITIONS)
EXPECTED_EPISODES_PER_UNIT = 24
EXPECTED_EPISODES = EXPECTED_UNITS * EXPECTED_EPISODES_PER_UNIT
EXPECTED_CLAIMS = EXPECTED_EPISODES * len(PREDICATES)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    return json.loads(payload), payload


def _unit_key(unit: dict[str, Any]) -> tuple[str, int]:
    return str(unit["communication_condition"]), int(unit["seed"])


def _per_unit_matches(
    left: dict[str, Any], right: dict[str, Any]
) -> tuple[bool, dict[str, dict[str, object]]]:
    left_units = {_unit_key(unit): unit for unit in left["units"]}
    right_units = {_unit_key(unit): unit for unit in right["units"]}
    expected = {(condition, seed) for condition in CONDITIONS for seed in SEEDS}
    rows: dict[str, dict[str, object]] = {}
    all_match = set(left_units) == set(right_units) == expected
    for condition, seed in sorted(expected):
        key = (condition, seed)
        left_bytes = _canonical(left_units.get(key))
        right_bytes = _canonical(right_units.get(key))
        match = left_bytes == right_bytes
        all_match = all_match and match
        rows[f"{condition}:{seed}"] = {
            "match": match,
            "left_sha256": _sha256(left_bytes),
            "right_sha256": _sha256(right_bytes),
        }
    return all_match, rows


def _expected_evidence_from_trace(
    observed_trace: dict[str, Any],
) -> dict[tuple[str, str], dict[str, object]]:
    expected: dict[tuple[str, str], dict[str, object]] = {}
    for unit in observed_trace.get("units", []):
        condition = str(unit.get("communication_condition"))
        seed = int(unit.get("seed"))
        scope = f"o0:{condition}:{seed}"
        for ordinal, episode in enumerate(unit.get("episodes", []), start=1):
            subject = str(episode.get("mission_id"))
            values = {
                "event_type": EVENT_TYPE,
                "context": episode.get("context"),
                "lead_skill": LEAD_SKILL,
                "support_skill": SUPPORT_SKILL,
                "participant_a": episode.get("agent_a"),
                "action_a": episode.get("action_a"),
                "participant_b": episode.get("agent_b"),
                "action_b": episode.get("action_b"),
                "outcome": "success" if episode.get("success") is True else "failure",
            }
            key = (scope, subject)
            if key in expected:
                raise ValueError(f"duplicate expected O0 event identity: {key}")
            expected[key] = {"observed_at": ordinal, "values": values}
    return expected


def _evidence_gate(
    evidence: dict[str, Any],
    raw_bytes: bytes,
    observed_trace: dict[str, Any],
) -> tuple[bool, dict[str, object]]:
    claims = evidence.get("claims", [])
    predicates = Counter(str(claim.get("predicate")) for claim in claims)
    claim_ids = [str(claim.get("claim_id")) for claim in claims]
    source_ids = [str(claim.get("source_id")) for claim in claims]

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        grouped[(str(claim.get("scope_id")), str(claim.get("subject")))].append(claim)

    expected_events = _expected_evidence_from_trace(observed_trace)
    expected_scopes = {f"o0:{condition}:{seed}" for condition in CONDITIONS for seed in SEEDS}
    scopes = {str(claim.get("scope_id")) for claim in claims}
    event_groups_complete = len(grouped) == EXPECTED_EPISODES
    provenance_valid = True
    source_identity_valid = True
    trace_values_valid = set(grouped) == set(expected_events)
    ordinal_events: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))

    for (scope, subject), rows in grouped.items():
        row_predicates = {str(row.get("predicate")) for row in rows}
        if len(rows) != len(PREDICATES) or row_predicates != set(PREDICATES):
            event_groups_complete = False
        observed_values = {int(row.get("observed_at", -1)) for row in rows}
        if len(observed_values) != 1:
            provenance_valid = False
            continue
        observed_at = next(iter(observed_values))
        ordinal_events[scope][observed_at].add(subject)

        expected_event = expected_events.get((scope, subject))
        if expected_event is None:
            trace_values_valid = False
        else:
            trace_values_valid = trace_values_valid and observed_at == expected_event["observed_at"]
            expected_values = expected_event["values"]
            actual_values = {str(row.get("predicate")): row.get("object") for row in rows}
            trace_values_valid = trace_values_valid and actual_values == expected_values

        for row in rows:
            predicate = str(row.get("predicate"))
            expected_source = f"{scope}:{subject}:{predicate}"
            source_identity_valid = (
                source_identity_valid and row.get("source_id") == expected_source
            )
            provenance_valid = provenance_valid and (
                row.get("observed_by") == OBSERVER_ID
                and row.get("source_class") == SOURCE_CLASS
                and row.get("confidence") == 1.0
                and row.get("direct") is True
                and row.get("valid_from") is None
                and row.get("valid_until") is None
            )

    ordinals_valid = set(ordinal_events) == expected_scopes
    for scope in expected_scopes:
        rows = ordinal_events.get(scope, {})
        ordinals_valid = ordinals_valid and set(rows) == set(range(1, 25))
        ordinals_valid = ordinals_valid and all(len(subjects) == 1 for subjects in rows.values())

    hidden_tokens = (
        b"practice_by_skill",
        b"IndividualState",
        b"RelationshipStateStore",
        b"pair_memories",
        b"partner_models",
        b"teamwork_models",
        b"JointController",
        b"JointEnvironment",
        b"evaluator",
        b"oracle",
    )
    hidden_hits = [token.decode() for token in hidden_tokens if token in raw_bytes]

    details: dict[str, object] = {
        "claim_count": len(claims),
        "expected_claim_count": EXPECTED_CLAIMS,
        "unique_claim_ids": len(set(claim_ids)),
        "unique_source_ids": len(set(source_ids)),
        "event_group_count": len(grouped),
        "expected_event_group_count": EXPECTED_EPISODES,
        "scopes": sorted(scopes),
        "expected_scopes": sorted(expected_scopes),
        "predicate_counts": {key: predicates[key] for key in sorted(predicates)},
        "event_groups_complete": event_groups_complete,
        "provenance_valid": provenance_valid,
        "source_identity_valid": source_identity_valid,
        "trace_values_valid": trace_values_valid,
        "ordinals_valid": ordinals_valid,
        "hidden_state_hits": hidden_hits,
    }
    passed = (
        evidence.get("schema") == "o0-contextgraph-evidence-v0.1"
        and len(claims) == EXPECTED_CLAIMS
        and len(set(claim_ids)) == EXPECTED_CLAIMS
        and len(set(source_ids)) == EXPECTED_CLAIMS
        and len(expected_events) == EXPECTED_EPISODES
        and scopes == expected_scopes
        and predicates == Counter({predicate: EXPECTED_EPISODES for predicate in PREDICATES})
        and event_groups_complete
        and provenance_valid
        and source_identity_valid
        and trace_values_valid
        and ordinals_valid
        and not hidden_hits
    )
    return passed, details


def _static_isolation_gate() -> tuple[bool, dict[str, object]]:
    env_parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    controller_parameters = set(inspect.signature(JointController.choose_action).parameters)
    forbidden_inputs = {"graph", "context_graph", "evidence", "claims", "observer", "observatory"}

    module_path = Path(inspect.getsourcefile(joint_learning) or "")
    tree = ast.parse(module_path.read_text())
    forbidden_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if any(
                token in name
                for token in (
                    "resonance_contextgraph",
                    "context_graph_adapter",
                    "context_graph_runtime",
                    "observatory",
                )
            ):
                forbidden_imports.append(name)

    init_parameters = set(inspect.signature(ContextGraphObservatory.__init__).parameters)
    observe_parameters = set(inspect.signature(ContextGraphObservatory.observe).parameters)
    public_callables = sorted(
        name
        for name, value in vars(ContextGraphObservatory).items()
        if not name.startswith("_") and callable(value)
    )
    observer_api_valid = (
        init_parameters == {"self", "scope_id"}
        and observe_parameters == {"self", "mission", "episode"}
        and set(public_callables) == {"observe", "evidence"}
    )

    details: dict[str, object] = {
        "environment_forbidden_inputs": sorted(env_parameters & forbidden_inputs),
        "controller_forbidden_inputs": sorted(controller_parameters & forbidden_inputs),
        "w4a_forbidden_imports": sorted(forbidden_imports),
        "observer_init_parameters": sorted(init_parameters),
        "observer_observe_parameters": sorted(observe_parameters),
        "observer_public_callables": public_callables,
        "historical_substrate_enabled": HISTORICAL_SUBSTRATE_ENABLED,
    }
    passed = (
        not (env_parameters & forbidden_inputs)
        and not (controller_parameters & forbidden_inputs)
        and not forbidden_imports
        and observer_api_valid
        and HISTORICAL_SUBSTRATE_ENABLED is False
    )
    return passed, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-trace", type=Path, required=True)
    parser.add_argument("--candidate-trace", type=Path, required=True)
    parser.add_argument("--observatory-trace", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--candidate-head", required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()

    frozen, frozen_bytes = _load(args.frozen_trace)
    candidate, candidate_bytes = _load(args.candidate_trace)
    observed, observed_bytes = _load(args.observatory_trace)
    evidence, evidence_bytes = _load(args.evidence)

    hook_compatibility, hook_units = _per_unit_matches(frozen, candidate)
    live_non_interference, live_units = _per_unit_matches(candidate, observed)
    evidence_complete, evidence_details = _evidence_gate(evidence, evidence_bytes, observed)
    static_isolation, isolation_details = _static_isolation_gate()

    trace_shapes_valid = all(
        payload.get("schema") == "o0-world-trace-v0.1"
        and len(payload.get("units", [])) == EXPECTED_UNITS
        and all(
            len(unit.get("episodes", [])) == EXPECTED_EPISODES_PER_UNIT
            for unit in payload["units"]
        )
        for payload in (frozen, candidate, observed)
    )

    gates = {
        "hook_compatibility": hook_compatibility and frozen_bytes == candidate_bytes,
        "live_non_interference": live_non_interference and candidate_bytes == observed_bytes,
        "evidence_completeness_and_hidden_state_exclusion": evidence_complete,
        "causal_isolation": static_isolation,
        "trace_shape": trace_shapes_valid,
    }
    passed = all(gates.values())
    result = {
        "schema": "o0-result-v0.1",
        "classification": (
            "observatory_non_interference_pass"
            if passed
            else "observatory_non_interference_failed"
        ),
        "gates": gates,
        "hook_compatibility_units": hook_units,
        "live_non_interference_units": live_units,
        "evidence": evidence_details,
        "causal_isolation": isolation_details,
        "sha256": {
            "frozen_base_trace": _sha256(frozen_bytes),
            "candidate_baseline_trace": _sha256(candidate_bytes),
            "observatory_trace": _sha256(observed_bytes),
            "contextgraph_evidence": _sha256(evidence_bytes),
        },
    }
    manifest = {
        "schema": "o0-manifest-v0.1",
        "north_star_issue": 111,
        "preregistration_issue": 113,
        "frozen_world_base": FROZEN_WORLD_BASE,
        "candidate_head": args.candidate_head,
        "contextgraph_commit": CONTEXTGRAPH_COMMIT,
        "contextgraph_release_metadata": "v0.1.0",
        "integration_mode": "observer-only",
        "historical_substrate_enabled": False,
        "participant_query_access": False,
        "seeds": list(SEEDS),
        "communication_conditions": {
            "communication-0": 0,
            "communication-1": 1,
        },
        "cycles": [
            "o0-context-alpha",
            "o0-context-beta",
            "o0-context-alpha",
            "o0-context-beta",
        ],
        "pair_order": [
            ["agent-a", "agent-b"],
            ["agent-c", "agent-d"],
            ["agent-a", "agent-c"],
            ["agent-b", "agent-d"],
            ["agent-a", "agent-d"],
            ["agent-b", "agent-c"],
        ],
        "agents": {
            "agent-a": {"planning": 9, "verification": 1},
            "agent-b": {"planning": 9, "verification": 1},
            "agent-c": {"planning": 1, "verification": 9},
            "agent-d": {"planning": 1, "verification": 9},
        },
        "mission_skills": {"lead": LEAD_SKILL, "support": SUPPORT_SKILL},
        "expected_counts": {
            "units_per_arm": EXPECTED_UNITS,
            "episodes_per_unit": EXPECTED_EPISODES_PER_UNIT,
            "episodes_per_arm": EXPECTED_EPISODES,
            "claims_per_episode": len(PREDICATES),
            "instrumented_claims": EXPECTED_CLAIMS,
        },
        "authoritative_files": [
            "frozen-base-trace.json",
            "candidate-baseline-trace.json",
            "observatory-trace.json",
            "contextgraph-evidence.json",
            "o0-result.json",
            "o0-manifest.json",
        ],
    }

    args.result_output.parent.mkdir(parents=True, exist_ok=True)
    args.result_output.write_bytes(_canonical(result))
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_bytes(_canonical(manifest))

    print(json.dumps({"classification": result["classification"], "gates": gates}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
