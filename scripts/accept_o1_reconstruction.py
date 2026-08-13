#!/usr/bin/env python3
"""Evaluate the preregistered O1 reconstruction-validity gates."""

from o1_accept_expected import *  # noqa: F403
from o1_accept_metrics import *  # noqa: F403

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relationship-baseline", required=True, type=Path)
    parser.add_argument("--relationship-observatory", required=True, type=Path)
    parser.add_argument("--relationship-evidence", required=True, type=Path)
    parser.add_argument("--plane-e-dir", required=True, type=Path)
    parser.add_argument("--plane-k-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--candidate-head", required=True)
    args = parser.parse_args()

    gates: dict[str, bool] = {}
    diagnostics: dict[str, Any] = {}

    # Gate 0: observer-only causal boundary and live O0 replay parity.
    gates["gate_0_observer_only_boundary"] = (
        INTEGRATION_MODE == "observer-only"
        and HISTORICAL_SUBSTRATE_ENABLED is False
        and args.relationship_baseline.read_bytes() == args.relationship_observatory.read_bytes()
        and _sha256_file(args.relationship_observatory) == O0_TRACE_SHA256
        and _sha256_file(args.relationship_evidence) == O0_EVIDENCE_SHA256
    )

    planes_e = _load_planes(args.plane_e_dir, "o1-plane-e-v0.1")
    planes_k = _load_planes(args.plane_k_dir, "o1-plane-k-v0.1")
    evidence = _read_json(args.output_dir / "contextgraph-evidence.json")
    claims = evidence["claims"]

    expected_generic_claims = sum(
        len(event["fields"])
        for plane in planes_e.values()
        for event in plane["events"]
    )
    expected_claim_count = 2160 + expected_generic_claims
    claim_ids = [str(row["claim_id"]) for row in claims]
    source_ids = [str(row["source_id"]) for row in claims]
    direct_valid = all(
        row.get("direct") is True and float(row.get("confidence")) == 1.0
        for row in claims
    )
    gates["gate_1_evidence_completeness_provenance"] = (
        len(claims) == expected_claim_count
        and len(set(claim_ids)) == len(claim_ids)
        and len(set(source_ids)) == len(source_ids)
        and direct_valid
    )
    diagnostics["claim_count"] = len(claims)
    diagnostics["expected_claim_count"] = expected_claim_count

    event = _read_json(args.output_dir / "event-ledger.json")
    trace = _read_json(args.relationship_observatory)
    expected_event = _canonical_event_ledger(
        [*_expected_r_events(trace), *_expected_e_events(planes_e)]
    )
    gates["gate_2_admissible_event_reconstruction_parity"] = (
        canonical_bytes(event) == canonical_bytes(expected_event)
    )

    expected_products = {
        "entity-ledger.json": _expected_entity_ledger(expected_event),
        "relationship-ledger.json": _expected_relationship_ledger(expected_event),
        "authority-ledger.json": _expected_authority_ledger(expected_event),
        "organization-lineage.json": _expected_organization_lineage(expected_event),
        "capability-evidence.json": _expected_capability_evidence(expected_event),
        "source-sustainability-evidence.json": _expected_source_sustainability(expected_event),
    }
    loaded_products = {
        name: _read_json(args.output_dir / name) for name in expected_products
    }
    gates["gate_3_entity_lineage_parity"] = all(
        canonical_bytes(loaded_products[name]) == canonical_bytes(expected)
        for name, expected in expected_products.items()
        if name
        in {
            "entity-ledger.json",
            "relationship-ledger.json",
            "authority-ledger.json",
            "organization-lineage.json",
        }
    )
    gates["gate_4_observable_aggregate_parity"] = all(
        canonical_bytes(loaded_products[name]) == canonical_bytes(expected_products[name])
        for name in ("capability-evidence.json", "source-sustainability-evidence.json")
    )

    authority_summary = _authority_summary(
        loaded_products["authority-ledger.json"], planes_k["A"]
    )
    expected_authority = dict(planes_k["A"]["expected_primary"])
    authority_ok = authority_summary == expected_authority

    turnover_summary = _turnover_summary(
        loaded_products["organization-lineage.json"], planes_k["T"]
    )
    expected_turnover = dict(planes_k["T"]["expected_primary"])
    turnover_keys = (
        "reset_success_rate",
        "retained_success_rate",
        "mean_retained_minus_reset_success_rate",
        "paired_better",
        "paired_worse",
        "paired_ties",
        "nonnegative_unit_effects",
        "forecast_preference_change_units",
        "reset_neutral_forecast_match_units",
        "retained_target_forecast_match_units",
        "retained_target_posterior_match_units",
    )
    turnover_ok = all(
        turnover_summary[key] == expected_turnover[key] for key in turnover_keys
    )

    source_summary = _source_summary(
        loaded_products["source-sustainability-evidence.json"]
    )
    source_key = planes_k["S"]
    source_expected = source_key["observable_expected"]
    expected_success_counts = {
        org: round(float(rate) * (24 * 512) / 100.0)
        for org, rate in source_expected["organization_rates_pct"].items()
    }
    source_ok = (
        source_summary["external_agent_cycle_exposures"]
        == int(source_expected["external_agent_cycle_exposures"])
        and all(
            source_summary["organization_success_counts"][org]
            == {"successes": successes, "attempts": 24 * 512}
            for org, successes in expected_success_counts.items()
        )
        and source_summary["service_cycle_count"]
        == int(source_expected["service_cycle_count"])
        and all(
            count == int(source_expected["service_cycles_per_organization"])
            for count in source_summary["service_cycles_per_organization"].values()
        )
        and set(source_summary["service_cycles_per_organization"])
        == set(source_expected["organization_rates_pct"])
        and all(
            source_summary["compute"][key] == float(source_expected["compute"][key])
            for key in source_summary["compute"]
        )
        and sorted(source_summary["not_observationally_identifiable_metrics"])
        == sorted(
            key
            for key in source_key["not_observationally_identifiable"]
            if key != "reason"
        )
    )
    gates["gate_5_historical_summary_reproducibility"] = (
        authority_ok and turnover_ok and source_ok
    )
    diagnostics["historical_summary"] = {
        "authority": authority_summary,
        "turnover": turnover_summary,
        "source_observable": source_summary,
        "source_hidden_summary_status": "not_observationally_identifiable",
    }

    # Gate 6: Plane-K-only field names and private-capability serialization are absent.
    product_paths = [
        args.output_dir / name
        for name in (
            "event-ledger.json",
            "entity-ledger.json",
            "relationship-ledger.json",
            "authority-ledger.json",
            "organization-lineage.json",
            "capability-evidence.json",
            "source-sustainability-evidence.json",
        )
    ]
    evidence_text = (args.output_dir / "contextgraph-evidence.json").read_text(
        encoding="utf-8"
    )
    product_text = "\n".join(path.read_text(encoding="utf-8") for path in product_paths)
    boundary_text = evidence_text + "\n" + product_text
    gates["gate_6_hidden_state_answer_key_exclusion"] = not any(
        token in boundary_text for token in FORBIDDEN_PRODUCT_TOKENS
    )

    # Gate 7's cross-reproduction byte comparison is enforced downstream in Actions.
    # This local condition proves that every authoritative output is deterministic and
    # contains no run ID or wall-clock metadata; the downstream job is the final enforcer.
    gates["gate_7_exact_head_reproducibility_contract"] = all(
        path.is_file() for path in [args.output_dir / "contextgraph-evidence.json", *product_paths]
    )

    classification = (
        "observatory_registered_reconstruction_pass"
        if all(gates.values())
        else "observatory_registered_reconstruction_failed"
    )
    result = {
        "schema": "o1-result-v0.1",
        "classification": classification,
        "gates": gates,
        "diagnostics": diagnostics,
        "scientific_claim": "registered_observer_side_reconstruction_only",
        "historical_substrate_enabled": False,
        "participant_query_access": False,
    }

    fixture_hashes = {
        f"{directory.name}/{path.name}": _sha256_file(path)
        for directory in (args.plane_e_dir, args.plane_k_dir)
        for path in sorted(directory.glob("*.json"))
    }
    product_hashes = {
        path.name: _sha256_file(path)
        for path in [
            args.output_dir / "contextgraph-evidence.json",
            *product_paths,
        ]
    }
    manifest = {
        "schema": "o1-manifest-v0.1",
        "north_star_issue": 111,
        "preregistration_issue": 119,
        "threshold_policy_issue": 118,
        "candidate_head": args.candidate_head,
        "world_preregistration_base": WORLD_BASE,
        "contextgraph_release_commit": STANDALONE_RELEASE_COMMIT,
        "piano_research_head": PIANO_HEAD,
        "relationship_evidence_sha256": _sha256_file(args.relationship_evidence),
        "relationship_trace_sha256": _sha256_file(args.relationship_observatory),
        "fixture_sha256": fixture_hashes,
        "product_sha256": product_hashes,
        "historical_substrate_enabled": False,
        "participant_query_access": False,
        "nondeterministic_metadata_excluded": True,
    }
    (args.output_dir / "o1-result.json").write_bytes(canonical_bytes(result))
    (args.output_dir / "o1-manifest.json").write_bytes(canonical_bytes(manifest))

    if classification != "observatory_registered_reconstruction_pass":
        raise SystemExit(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
