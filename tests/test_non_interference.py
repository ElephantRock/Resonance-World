from resonance_world.non_interference import FieldRunObservation, compare_observations


def observation(*, market_hash: str = "abc", metric: float = 0.41, overhead: float = 0.0):
    return FieldRunObservation(
        field_id="field-a",
        checkpoint_id="checkpoint-001",
        state_hashes={
            "market": market_hash,
            "reputation": "def",
            "traces": "ghi",
            "lifecycle": "jkl",
        },
        emergence_metrics={"specialization_entropy": metric},
        total_runtime_seconds=100.0,
        world_instrumentation_seconds=overhead,
    )


def test_identical_behavior_with_bounded_overhead_passes() -> None:
    report = compare_observations(observation(), observation(overhead=4.0))

    assert report.passed
    assert report.behavior_identical
    assert report.overhead_ratio == 0.04


def test_state_drift_fails_even_with_low_overhead() -> None:
    report = compare_observations(
        observation(), observation(market_hash="changed", overhead=1.0)
    )

    assert not report.passed
    assert report.differing_hashes == ("market",)


def test_excessive_observation_overhead_fails() -> None:
    report = compare_observations(observation(), observation(overhead=7.0))

    assert report.behavior_identical
    assert not report.overhead_within_bound
    assert not report.passed
