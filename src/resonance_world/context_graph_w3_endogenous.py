ill,
            )
            candidate = (score, f"{lead_id}::{support_id}", lead_id, support_id)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return None if best is None else (best[2], best[3])


def _expected_success(
    field: EndogenousField,
    mission: CG4Mission,
    pair: tuple[str, str],
) -> float:
    environment = JointEnvironment()
    public = mission.public(field.field_id)
    return environment.role_probability(
        field.states[pair[0]], public.lead_skill
    ) * environment.role_probability(field.states[pair[1]], public.support_skill)


def _oracle_pair(field: EndogenousField, mission: CG4Mission) -> tuple[str, str]:
    best: tuple[float, str, str, str] | None = None
    for lead_id in sorted(field.current_members):
        for support_id in sorted(field.current_members):
            if lead_id == support_id:
                continue
            score = _expected_success(field, mission, (lead_id, support_id))
            candidate = (score, f"{lead_id}::{support_id}", lead_id, support_id)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    if best is None:
        raise ValueError("field does not contain an oracle pair")
    return best[2], best[3]


def _evaluate_pair_trials(
    field: EndogenousField,
    mission: CG4Mission,
    pair: tuple[str, str] | None,
    *,
    trials: int,
) -> int:
    if pair is None or not set(pair).issubset(field.current_members):
        return 0
    environment = JointEnvironment()
    public = mission.public(field.field_id)
    first = field.states[pair[0]]
    second = field.states[pair[1]]
    return sum(
        environment.evaluate(
            first,
            second,
            public,
            JointAction(first.agent_id, "lead"),
            JointAction(second.agent_id, "support"),
            seed=trial,
        )
        for trial in range(trials)
    )


def evaluate_fields(
    fields: list[EndogenousField],
    missions: list[CG4Mission],
    *,
    context_budget: int,
    min_confidence: float,
    evaluation_trials: int,
) -> dict[Arm, CG4Metrics]:
    accumulators: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "decisions": 0,
            "successes": 0,
            "trials": 0,
            "expected_success_total": 0.0,
            "oracle_expected_total": 0.0,
            "regret_total": 0.0,
            "oracle_pair_matches": 0,
            "invalid_selections": 0,
            "context_claims": 0,
            "provenance_complete_claims": 0,
        }
    )
    for field_item in fields:
        shuffled = _shuffle_identity(field_item)
        beliefs_before = field_item.belief_snapshot
        for mission in missions:
            contexts: dict[Arm, tuple[LiveClaim, ...]] = {
                "local_only": _compile_local(
                    field_item,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "pooled_flat": _compile_flat(
                    field_item,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "endogenous_graph": _compile_graph(
                    field_item,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    respect_temporal_order=True,
                ),
                "shuffled_graph": _compile_graph(
                    shuffled,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    respect_temporal_order=True,
                ),
                "stale_graph": _compile_graph(
                    field_item,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    respect_temporal_order=False,
                ),
                "conflicted_graph": _compile_graph(
                    field_item,
                    mission,
                    budget=context_budget,
                    min_confidence=0.0,
                    respect_temporal_order=True,
                ),
                "oracle": (),
            }
            oracle_pair = _oracle_pair(field_item, mission)
            oracle_expected = _expected_success(field_item, mission, oracle_pair)
            for arm, context in contexts.items():
                pair = (
                    oracle_pair
                    if arm == "oracle"
                    else _estimate_pair(
                        context,
                        mission,
                        min_confidence=(
                            0.0 if arm == "conflicted_graph" else min_confidence
                        ),
                        respect_temporal_order=arm != "stale_graph",
                    )
                )
                invalid = pair is None or not set(pair).issubset(field_item.current_members)
                expected = (
                    0.0
                    if invalid or pair is None
                    else _expected_success(field_item, mission, pair)
                )
                successes = _evaluate_pair_trials(
                    field_item,
                    mission,
                    pair,
                    trials=evaluation_trials,
                )
                row = accumulators[arm]
                row["decisions"] += 1
                row["successes"] += successes
                row["trials"] += evaluation_trials
                row["expected_success_total"] += expected
                row["oracle_expected_total"] += oracle_expected
                row["regret_total"] += oracle_expected - expected
                row["oracle_pair_matches"] += int(pair == oracle_pair)
                row["invalid_selections"] += int(invalid)
                row["context_claims"] += len(context)
                row["provenance_complete_claims"] += sum(
                    bool(claim.source_id and claim.source_class and claim.observed_by)
                    for claim in context
                )
        if field_item.belief_snapshot != beliefs_before:
            raise AssertionError("retrieval mutated agent-local belief state")
    return {
        arm: CG4Metrics(arm=arm, **values)  # type: ignore[arg-type]
        for arm, values in accumulators.items()
    }


def diagnostics(fields: list[EndogenousField]) -> dict[str, int]:
    return {
        "emitted_claims": sum(field.emitted_claims for field in fields),
        "duplicate_observation_groups": sum(
            field.duplicate_observation_groups for field in fields
        ),
        "conflicting_observation_groups": sum(
            field.conflicting_observation_groups for field in fields
        ),
        "low_confidence_claims": sum(field.low_confidence_claims for field in fields),
        "departed_members": sum(len(field.departed_members) for field in fields),
        "posthoc_imported_claims": 0,
        "historical_outcome_rows_consumed": 0,
    }


def metric_row(metrics: CG4Metrics) -> dict[str, object]:
    return {
        "arm": metrics.arm,
        "decisions": metrics.decisions,
        "successes": metrics.successes,
        "trials": metrics.trials,
        "mission_success_rate": metrics.mission_success_rate,
        "mean_expected_success": metrics.mean_expected_success,
        "mean_oracle_expected_success": metrics.mean_oracle_expected_success,
        "mean_regret": metrics.mean_regret,
        "oracle_pair_matches": metrics.oracle_pair_matches,
        "oracle_pair_rate": metrics.oracle_pair_rate,
        "invalid_selections": metrics.invalid_selections,
        "invalid_selection_rate": metrics.invalid_selection_rate,
        "context_claims": metrics.context_claims,
        "mean_context_claims": metrics.mean_context_claims,
        "provenance_completeness": metrics.provenance_completeness,
    }
