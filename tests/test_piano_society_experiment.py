from experiments.piano_society.harness import (
    generate_frames,
    run_baseline,
    run_experiment,
    run_treatment,
    summarize,
)


def test_paired_arms_share_the_same_raw_frames() -> None:
    frames = generate_frames(
        seed=1729,
        scale=10,
        steps_per_agent=8,
        proposal_disagreement_rate=0.25,
    )

    baseline = run_baseline(frames, failure_rate=0.18)
    treatment = run_treatment(frames, failure_rate=0.18)

    assert len(baseline) == len(treatment) == len(frames)
    assert [(row.seed, row.scale, row.agent_id, row.step) for row in baseline] == [
        (row.seed, row.scale, row.agent_id, row.step) for row in treatment
    ]


def test_treatment_removes_synthetic_cross_channel_contradiction() -> None:
    frames = generate_frames(
        seed=3253,
        scale=50,
        steps_per_agent=20,
        proposal_disagreement_rate=0.25,
    )

    baseline = summarize(run_baseline(frames, failure_rate=0.18))
    treatment = summarize(run_treatment(frames, failure_rate=0.18))

    assert baseline["cross_channel_contradiction_rate"] > 0.0
    assert treatment["cross_channel_contradiction_rate"] == 0.0
    assert treatment["unsupported_success_claim_rate"] == 0.0


def test_phase_zero_cannot_be_misreported_as_scientific_evidence() -> None:
    config = {
        "experiment": "piano-society-runtime-v0",
        "seeds": [1729],
        "scales": [10],
        "steps_per_agent": 5,
        "proposal_disagreement_rate": 0.25,
        "environment_failure_rate": 0.18,
    }

    result = run_experiment(config)

    assert result["phase"] == "instrumentation-validation"
    assert result["scientific_claim_allowed"] is False
