#!/usr/bin/env python3
"""Materialize the frozen O1 benchmark planes from accepted historical artifacts."""

from o1_materialize_piano import *  # noqa: F403

def _weights(requirements: dict[str, float]) -> dict[str, float]:
    total = sum(requirements.values())
    return {skill: value / total for skill, value in requirements.items()}


def _label_fit(label: object, skill_weights: dict[str, float]) -> float:
    if label is None:
        return 0.0
    return min(1.0, skill_weights.get(str(label), 0.0) * max(1, len(skill_weights)))


def _public_score(candidate: dict[str, Any], lead_skill: str, support_skill: str) -> float:
    weights = {
        "home_success_rate": 0.30,
        "bid_win_rate": 0.20,
        "mean_bid_confidence": 0.10,
        "experience": 0.10,
        "dominant_host_fit": 0.20,
        "secondary_host_fit": 0.10,
        "experience_scale": 12.0,
    }
    mission_weights = _weights({lead_skill: 0.5, support_skill: 0.5})
    features = candidate["public_features"]
    profile = candidate["public_mission_profile"]
    values = {
        "home_success_rate": float(features["home_success_rate"]),
        "bid_win_rate": float(features["bid_win_rate"]),
        "mean_bid_confidence": float(features["mean_bid_confidence"]),
        "experience": min(
            1.0, float(features["completed_tasks"]) / weights["experience_scale"]
        ),
        "dominant_host_fit": _label_fit(
            profile.get("dominant_success_skill"), mission_weights
        ),
        "secondary_host_fit": _label_fit(
            profile.get("secondary_success_skill"), mission_weights
        ),
    }
    score = sum(float(weights[key]) * values[key] for key in values)
    return min(1.0, max(0.0, score))


def _cycle_organizations(cycle: int) -> list[dict[str, str]]:
    rows = [
        {"organization_id": org, "lead_skill": lead, "support_skill": support}
        for org, lead, support in W9_ORGANIZATIONS
    ]
    shifts = sum(1 for shift in (6, 12, 18) if shift <= cycle)
    if not shifts:
        return rows
    for row in rows:
        row["lead_skill"] = W9_SKILLS[
            (W9_SKILLS.index(row["lead_skill"]) + shifts) % len(W9_SKILLS)
        ]
        row["support_skill"] = W9_SKILLS[
            (W9_SKILLS.index(row["support_skill"]) + shifts) % len(W9_SKILLS)
        ]
    return rows


def _w9_offers(candidates: list[dict[str, Any]], rows: list[dict[str, str]], cycle: int):
    window = f"w9-06:replication:selected:{cycle}"
    offers: list[dict[str, Any]] = []
    for organization in rows:
        org = organization["organization_id"]
        ranked = sorted(
            (
                (
                    _public_score(
                        candidate,
                        organization["lead_skill"],
                        organization["support_skill"],
                    ),
                    str(candidate["field_id"]),
                    str(candidate["agent_id"]),
                    candidate,
                )
                for candidate in candidates
            ),
            key=lambda item: (-item[0], item[1], item[2]),
        )
        for rank, (score, field_id, agent_id, _candidate) in enumerate(ranked[:8], 1):
            offers.append(
                {
                    "offer_id": f"{window}:{org}:{rank:02d}:{agent_id}",
                    "organization_id": org,
                    "agent_id": agent_id,
                    "field_id": field_id,
                    "bid": 30 + int(round(60 * score)),
                }
            )
    return offers


def _w9_allocate(offers: list[dict[str, Any]], excluded_fields: set[str]):
    balances = {org: 220 for org, _lead, _support in W9_ORGANIZATIONS}
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for offer in offers:
        if str(offer["field_id"]) not in excluded_fields:
            by_agent[str(offer["agent_id"])].append(offer)
    contracts: list[dict[str, Any]] = []
    for agent_id in sorted(by_agent):
        ranked = sorted(
            by_agent[agent_id],
            key=lambda row: (-int(row["bid"]), str(row["organization_id"]), str(row["offer_id"])),
        )
        winner = next(
            (
                row
                for row in ranked
                if balances[str(row["organization_id"])] >= int(row["bid"])
            ),
            None,
        )
        if winner is not None:
            balances[str(winner["organization_id"])] -= int(winner["bid"])
            contracts.append(winner)
    return contracts


def _seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _role_probability(practice: dict[str, int], skill: str) -> float:
    return min(0.94, 0.35 + 0.16 * math.sqrt(max(0, int(practice.get(skill, 0)))))


def _best_w9_pair(
    roster: list[str], states: dict[str, dict[str, int]], lead_skill: str, support_skill: str
) -> tuple[str, str] | None:
    if len(roster) < 2:
        return None
    best: tuple[float, str, str] | None = None
    for lead in roster:
        for support in roster:
            if lead == support:
                continue
            candidate = (
                _role_probability(states[lead], lead_skill)
                * _role_probability(states[support], support_skill),
                lead,
                support,
            )
            if best is None or candidate > best:
                best = candidate
    return None if best is None else (best[1], best[2])


def _w9_cycle_successes(
    cycle: int,
    organization: dict[str, str],
    roster: list[str],
    states: dict[str, dict[str, int]],
) -> tuple[int, tuple[str, str] | None]:
    pair = _best_w9_pair(
        roster, states, organization["lead_skill"], organization["support_skill"]
    )
    if pair is None:
        return 0, None
    lead, support = pair
    mission_id = f"w8-org:{organization['organization_id']}:w9-06:{cycle}"
    salt = f"w9-06:replication:selected:{cycle}:{organization['organization_id']}"
    lead_probability = _role_probability(states[lead], organization["lead_skill"])
    support_probability = _role_probability(states[support], organization["support_skill"])
    successes = 0
    for trial in range(512):
        seed = _seed(salt, mission_id, trial)
        lead_ok = _uniform("w4a", mission_id, seed, "lead") < lead_probability
        support_ok = _uniform("w4a", mission_id, seed, "support") < support_probability
        successes += int(lead_ok and support_ok)
    return successes, pair


def _source_planes(artifact: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = _zip_jsonl(artifact, "source/candidates.jsonl")
    capsules = _zip_jsonl(artifact, "source/capsules.private.jsonl")
    result_bytes = _zip_text(artifact, "w9-06-long-horizon.json").encode()
    if hashlib.sha256(result_bytes).hexdigest() != W9_06_SHA256:
        raise ValueError("W9-06 result bytes differ from accepted hash")
    result = json.loads(result_bytes)
    selected = result["arms"]["selected_W9"]
    source = {
        "accepted_w9_exact_head": "eaaa0c013cd878a5d0e1afa88bfc6d54e90ae371",
        "workflow_run": 31654273741,
        "artifact_id": 9163835188,
        "artifact_sha256": W9_ARTIFACT_SHA256,
        "w9_06_sha256": W9_06_SHA256,
    }
    alias_by_raw = {str(row["agent_id"]): _w9_alias(str(row["agent_id"])) for row in candidates}
    field_ordinals: dict[str, int] = defaultdict(int)
    events: list[dict[str, Any]] = []
    for row in candidates:
        field_id = str(row["field_id"])
        field_ordinals[field_id] += 1
        profile = row["public_mission_profile"]
        alias = alias_by_raw[str(row["agent_id"])]
        events.append(
            {
                "event_id": f"{field_id}:{alias}",
                "scope_id": f"o1:S:{field_id}",
                "observed_at": field_ordinals[field_id],
                "source_class": "world_public_source_observation",
                "fields": {
                    "event_type": "source_agent_public_record",
                    "source_id": field_id,
                    "agent_id": alias,
                    "source_evidence_sha256": str(row["source_evidence_sha256"]),
                    "dominant_success_skill": str(profile.get("dominant_success_skill")),
                    "secondary_success_skill": str(profile.get("secondary_success_skill")),
                },
            }
        )
    states = {
        str(row["agent_id"]): {
            str(skill): int(value) for skill, value in row["practice_by_skill"].items()
        }
        for row in capsules
    }
    field_ids = sorted({str(row["field_id"]) for row in candidates})
    service_rows: list[dict[str, Any]] = []
    totals = {org: 0 for org, _lead, _support in W9_ORGANIZATIONS}
    for cycle in range(24):
        organizations = _cycle_organizations(cycle)
        excluded: set[str] = set()
        if cycle in {8, 16}:
            excluded.add(field_ids[(cycle // 8) % len(field_ids)])
        contracts = _w9_allocate(_w9_offers(candidates, organizations, cycle), excluded)
        by_org: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for contract in contracts:
            by_org[str(contract["organization_id"])].append(contract)
        for organization in organizations:
            org = organization["organization_id"]
            roster_contracts = sorted(by_org[org], key=lambda row: str(row["agent_id"]))
            roster = [str(row["agent_id"]) for row in roster_contracts]
            for contract in roster_contracts:
                events.append(
                    {
                        "event_id": (
                            f"contract:{cycle:02d}:{org}:"
                            f"{alias_by_raw[str(contract['agent_id'])]}"
                        ),
                        "scope_id": "o1:S:w9-06:selected",
                        "observed_at": cycle + 1,
                        "source_class": "world_market_observation",
                        "fields": {
                            "event_type": "contract_service_right",
                            "cycle": str(cycle),
                            "organization_id": org,
                            "agent_id": alias_by_raw[str(contract["agent_id"])],
                            "source_id": str(contract["field_id"]),
                            "price": str(int(contract["bid"])),
                            "lead_skill": organization["lead_skill"],
                            "support_skill": organization["support_skill"],
                        },
                    }
                )
            successes, pair = _w9_cycle_successes(cycle, organization, roster, states)
            totals[org] += successes
            if pair is None:
                lead_alias = support_alias = ""
            else:
                lead_alias = alias_by_raw[pair[0]]
                support_alias = alias_by_raw[pair[1]]
                states[pair[0]][organization["lead_skill"]] = (
                    states[pair[0]].get(organization["lead_skill"], 0) + 1
                )
                states[pair[1]][organization["support_skill"]] = (
                    states[pair[1]].get(organization["support_skill"], 0) + 1
                )
            service_rows.append(
                {
                    "event_id": f"service:{cycle}:{org}",
                    "scope_id": "o1:S:w9-06:selected",
                    "observed_at": cycle + 1,
                    "source_class": "world_service_observation",
                    "fields": {
                        "event_type": "organization_service_cycle",
                        "cycle": str(cycle),
                        "organization_id": org,
                        "lead_skill": organization["lead_skill"],
                        "support_skill": organization["support_skill"],
                        "lead_agent_id": lead_alias,
                        "support_agent_id": support_alias,
                        "attempt_count": "512",
                        "success_count": str(successes),
                        "failure_count": str(512 - successes),
                    },
                }
            )
    expected_totals = {
        org: round(float(rate) * (24 * 512) / 100.0)
        for org, rate in selected["organization_rates_pct"].items()
    }
    if totals != expected_totals:
        raise ValueError(f"W9 deterministic service replay mismatch: {totals}")
    for org, _lead, _support in W9_ORGANIZATIONS:
        successes = totals[org]
        attempts = 24 * 512
        events.append(
            {
                "event_id": f"service-summary:{org}",
                "scope_id": "o1:S:w9-06:selected",
                "observed_at": 25,
                "source_class": "world_service_observation",
                "fields": {
                    "event_type": "organization_service_summary",
                    "organization_id": org,
                    "attempt_count": str(attempts),
                    "success_count": str(successes),
                    "failure_count": str(attempts - successes),
                    "success_rate": str(successes / attempts),
                },
            }
        )
    compute = selected["compute"]
    events.append(
        {
            "event_id": "observable-accounting",
            "scope_id": "o1:S:w9-06:selected",
            "observed_at": 26,
            "source_class": "world_accounting_observation",
            "fields": {
                "event_type": "observable_accounting_summary",
                "external_agent_cycle_exposures": str(
                    int(selected["external_agent_cycle_exposures"])
                ),
                "incremental_source_development_compute": str(
                    float(compute["incremental_source_development_compute"])
                ),
                "mission_execution_compute": str(float(compute["mission_execution_compute"])),
                "organization_coordination_compute": str(
                    float(compute["organization_coordination_compute"])
                ),
                "world_regulatory_estimation_compute": str(
                    float(compute["world_regulatory_estimation_compute"])
                ),
            },
        }
    )
    # The frozen fixture order intentionally places the cycle-level replay after the
    # accepted aggregate/accounting observations; reconstruction itself canonicalizes.
    events.extend(service_rows)
    key = {
        "schema": "o1-plane-k-v0.1",
        "family": "S",
        "source": source,
        "historical_classification": str(result["classification"]),
        "historical_long_horizon_gate": bool(result["long_horizon_gate"]),
        "historical_result_sha256": W9_06_SHA256,
        "observable_expected": {
            "external_agent_cycle_exposures": int(
                selected["external_agent_cycle_exposures"]
            ),
            "organization_rates_pct": {
                str(org): float(value)
                for org, value in selected["organization_rates_pct"].items()
            },
            "compute": {
                "incremental_source_development_compute": float(
                    compute["incremental_source_development_compute"]
                ),
                "mission_execution_compute": float(compute["mission_execution_compute"]),
                "organization_coordination_compute": float(
                    compute["organization_coordination_compute"]
                ),
                "world_regulatory_estimation_compute": float(
                    compute["world_regulatory_estimation_compute"]
                ),
            },
            "service_cycle_count": 72,
            "service_cycles_per_organization": 24,
        },
        "not_observationally_identifiable": {
            "compute_normalized_world_stock_growth": float(
                selected["compute_normalized_world_stock_growth"]
            ),
            "developmental_efficiency": selected["developmental_efficiency"],
            "mean_source_loss_pp": float(selected["mean_source_loss_pp"]),
            "service_efficiency": float(selected["service_efficiency"]),
            "source_accessible_capability_growth": float(
                selected["source_accessible_capability_growth"]
            ),
            "reason": (
                "historical W9-06 metrics depend on private capability/practice state or "
                "source-frontier diagnostics not present in admissible public events"
            ),
        },
    }
    return (
        {"schema": "o1-plane-e-v0.1", "family": "S", "source": source, "events": events},
        key,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase4c-artifact", required=True, type=Path)
    parser.add_argument("--phase5c-artifact", required=True, type=Path)
    parser.add_argument("--phase5c-source-artifact", required=True, type=Path)
    parser.add_argument("--w9-artifact", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    expected_artifacts = {
        args.phase4c_artifact: PHASE4C_ARTIFACT_SHA256,
        args.phase5c_artifact: PHASE5C_ARTIFACT_SHA256,
        args.phase5c_source_artifact: PHASE5C_SOURCE_SHA256,
        args.w9_artifact: W9_ARTIFACT_SHA256,
    }
    for path, expected in expected_artifacts.items():
        if _sha256(path) != expected:
            raise ValueError(f"historical artifact digest mismatch: {path}")

    authority_e, authority_k = _authority_planes(args.phase4c_artifact)
    turnover_e, turnover_k = _turnover_planes(
        args.phase5c_artifact, args.phase5c_source_artifact
    )
    source_e, source_k = _source_planes(args.w9_artifact)
    for name, value in (
        ("plane_e/authority.json", authority_e),
        ("plane_e/turnover.json", turnover_e),
        ("plane_e/source-sustainability.json", source_e),
        ("plane_k/authority.json", authority_k),
        ("plane_k/turnover.json", turnover_k),
        ("plane_k/source-sustainability.json", source_k),
    ):
        _write(args.output_root / name, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
