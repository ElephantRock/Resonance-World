: source_identity_valid,
        "ordinals_valid": ordinals_valid,
        "hidden_state_hits": hidden_hits,
    }
    passed = (
        evidence.get("schema") == "o0-contextgraph-evidence-v0.1"
        and len(claims) == EXPECTED_CLAIMS
        and len(set(claim_ids)) == EXPECTED_CLAIMS
        and len(set(source_ids)) == EXPECTED_CLAIMS
        and scopes == expected_scopes
        and predicates == Counter({predicate: EXPECTED_EPISODES for predicate in PREDICATES})
        and event_groups_complete
        and provenance_valid
        and source_identity_valid
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
    evidence_complete, evidence_details = _evidence_gate(evidence, evidence_bytes)
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
        "mission_skills": {"lead": "planning", "support": "verification"},
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
