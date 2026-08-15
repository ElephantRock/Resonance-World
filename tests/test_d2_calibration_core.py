from __future__ import annotations

from scripts.d2_calibration_core import (
    ACTIONS,
    descriptive_summary,
    features_set,
    generate_cases,
    labeled_feedback,
    policy_for,
    public_case,
    score_actions,
)


def test_generator_is_deterministic_and_disjointable() -> None:
    policy = policy_for(70000)
    source = generate_cases(rng_seed=70001, count=16, prefix="s", policy=policy)
    dest = generate_cases(
        rng_seed=70002,
        count=16,
        prefix="d",
        policy=policy,
        exclude_features=features_set(source),
    )
    assert source == generate_cases(rng_seed=70001, count=16, prefix="s", policy=policy)
    assert features_set(source).isdisjoint(features_set(dest))
    assert set(public_case(source[0])) == {"case_id", "features"}


def test_scoring_and_feedback() -> None:
    policy = policy_for(70010)
    cases = generate_cases(rng_seed=70011, count=4, prefix="s", policy=policy)
    truth = [case["correct_action"] for case in cases]
    assert score_actions(cases, truth) == 1.0
    wrong = [next(action for action in ACTIONS if action != correct) for correct in truth]
    assert score_actions(cases, wrong) == 0.0
    feedback = labeled_feedback(cases, truth)
    assert all(item["correct"] for item in feedback)


def test_descriptive_summary() -> None:
    pairs = []
    for index in range(3):
        pairs.append(
            {
                "arms": {
                    "fresh": {"final_score": 0.25},
                    "description_only": {"final_score": 0.25},
                    "reproduced": {"final_score": 0.75 + index * 0.01},
                    "source_developed": {"final_score": 0.8},
                }
            }
        )
    summary = descriptive_summary(pairs)
    assert summary["pair_count"] == 3
    assert summary["paired_contrasts"]["p1_reproduced_minus_description"]["mean"] > 0.5
