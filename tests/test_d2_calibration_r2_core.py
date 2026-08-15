from scripts.d2_calibration_r2_core import (
    ACTIONS,
    CHANCE_SCORE,
    correct_action,
    development_readiness,
    features_set,
    generate_balanced_cases,
    policy_for,
)


def test_policy_is_deterministic():
    assert policy_for(12345) == policy_for(12345)


def test_balanced_cases_are_unique_and_action_balanced():
    policy = policy_for(101)
    cases = generate_balanced_cases(
        rng_seed=202,
        count=32,
        prefix="x",
        policy=policy,
    )
    assert len(cases) == 32
    assert len(features_set(cases)) == 32
    counts = {action: 0 for action in ACTIONS}
    for case in cases:
        features = tuple(case["features"][f"f{i}"] for i in range(4))
        assert correct_action(policy, features) == case["correct_action"]
        counts[case["correct_action"]] += 1
    assert set(counts.values()) == {8}


def test_exclusion_is_exact():
    policy = policy_for(303)
    source = generate_balanced_cases(
        rng_seed=1,
        count=32,
        prefix="s",
        policy=policy,
    )
    destination = generate_balanced_cases(
        rng_seed=2,
        count=32,
        prefix="d",
        policy=policy,
        exclude_features=features_set(source),
    )
    assert features_set(source).isdisjoint(features_set(destination))


def test_chance_score_is_quarter():
    assert CHANCE_SCORE == 0.25


def test_development_readiness_gate():
    pairs = []
    for _ in range(8):
        pairs.append(
            {
                "arms": {
                    "fresh": {"final_score": 0.25},
                    "description_only": {"final_score": 0.25},
                    "reproduced": {"final_score": 0.60},
                    "source_developed": {
                        "final_score": 0.60,
                        "development_batch_scores": [0.40, 0.50, 0.55, 0.60],
                    },
                }
            }
        )
    readiness = development_readiness(pairs)
    assert readiness["all_gates_pass"] is True
    assert readiness["threshold_class"] == "conventional_development_readiness_not_inferential"
