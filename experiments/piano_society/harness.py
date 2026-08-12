"""Phase-0 coherence instrumentation for the PIANO-inspired society-runtime experiment.

This module is intentionally synthetic. It validates paired-arm measurement before any
live LLM or Resonance Field integration is introduced.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


class Intent(StrEnum):
    GATHER = "gather"
    TRADE = "trade"
    REST = "rest"


@dataclass(frozen=True, slots=True)
class RawFrame:
    """Exogenous input shared by baseline and treatment arms."""

    seed: int
    scale: int
    agent_id: int
    step: int
    cognitive_intent: Intent
    speech_proposal: Intent
    action_proposal: Intent
    environment_draw: float


@dataclass(frozen=True, slots=True)
class Outcome:
    arm: str
    seed: int
    scale: int
    agent_id: int
    step: int
    controller_intent: Intent
    spoken_intent: Intent
    action_intent: Intent
    action_succeeded: bool
    speech_claimed_success: bool


def _different(intent: Intent, rng: random.Random) -> Intent:
    alternatives = [candidate for candidate in Intent if candidate != intent]
    return rng.choice(alternatives)


def generate_frames(
    *,
    seed: int,
    scale: int,
    steps_per_agent: int,
    proposal_disagreement_rate: float,
) -> list[RawFrame]:
    """Generate one paired stream of raw module proposals and environment draws."""

    rng = random.Random(seed)
    intents = list(Intent)
    frames: list[RawFrame] = []
    for step in range(steps_per_agent):
        for agent_id in range(scale):
            cognitive = intents[(agent_id + step) % len(intents)]
            speech = (
                _different(cognitive, rng)
                if rng.random() < proposal_disagreement_rate
                else cognitive
            )
            action = (
                _different(cognitive, rng)
                if rng.random() < proposal_disagreement_rate
                else cognitive
            )
            frames.append(
                RawFrame(
                    seed=seed,
                    scale=scale,
                    agent_id=agent_id,
                    step=step,
                    cognitive_intent=cognitive,
                    speech_proposal=speech,
                    action_proposal=action,
                    environment_draw=rng.random(),
                )
            )
    return frames


def _action_succeeded(intent: Intent, environment_draw: float, failure_rate: float) -> bool:
    if intent == Intent.REST:
        return True
    return environment_draw >= failure_rate


def run_baseline(frames: Iterable[RawFrame], *, failure_rate: float) -> list[Outcome]:
    """Run independent speech/action channels without arbitration or acknowledgement."""

    outcomes: list[Outcome] = []
    for frame in frames:
        action_succeeded = _action_succeeded(
            frame.action_proposal,
            frame.environment_draw,
            failure_rate,
        )
        outcomes.append(
            Outcome(
                arm="baseline",
                seed=frame.seed,
                scale=frame.scale,
                agent_id=frame.agent_id,
                step=frame.step,
                controller_intent=frame.cognitive_intent,
                spoken_intent=frame.speech_proposal,
                action_intent=frame.action_proposal,
                action_succeeded=action_succeeded,
                speech_claimed_success=frame.speech_proposal != Intent.REST,
            )
        )
    return outcomes


def run_treatment(frames: Iterable[RawFrame], *, failure_rate: float) -> list[Outcome]:
    """Run a shared intention plus action acknowledgement before success claims."""

    outcomes: list[Outcome] = []
    for frame in frames:
        intent = frame.cognitive_intent
        action_succeeded = _action_succeeded(
            intent,
            frame.environment_draw,
            failure_rate,
        )
        outcomes.append(
            Outcome(
                arm="treatment",
                seed=frame.seed,
                scale=frame.scale,
                agent_id=frame.agent_id,
                step=frame.step,
                controller_intent=intent,
                spoken_intent=intent,
                action_intent=intent,
                action_succeeded=action_succeeded,
                speech_claimed_success=action_succeeded and intent != Intent.REST,
            )
        )
    return outcomes


def summarize(outcomes: list[Outcome]) -> dict[str, float | int]:
    """Compute arm-level coherence and grounding metrics."""

    if not outcomes:
        raise ValueError("outcomes must not be empty")

    observations = len(outcomes)
    actionable = sum(outcome.action_intent != Intent.REST for outcome in outcomes)
    contradictions = sum(
        outcome.spoken_intent != outcome.action_intent for outcome in outcomes
    )
    divergences = sum(
        outcome.controller_intent != outcome.action_intent for outcome in outcomes
    )
    unsupported_claims = sum(
        outcome.speech_claimed_success
        and (
            outcome.spoken_intent != outcome.action_intent
            or not outcome.action_succeeded
        )
        for outcome in outcomes
    )
    successful_actions = sum(
        outcome.action_succeeded and outcome.action_intent != Intent.REST
        for outcome in outcomes
    )

    return {
        "observations": observations,
        "cross_channel_contradiction_rate": contradictions / observations,
        "intent_action_divergence_rate": divergences / observations,
        "unsupported_success_claim_rate": unsupported_claims / observations,
        "task_success_rate": successful_actions / actionable if actionable else 0.0,
    }


def _load_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    """Execute paired baseline/treatment runs for every preregistered seed and scale."""

    rows: list[dict[str, Any]] = []
    for scale in config["scales"]:
        for seed in config["seeds"]:
            frames = generate_frames(
                seed=seed,
                scale=scale,
                steps_per_agent=config["steps_per_agent"],
                proposal_disagreement_rate=config["proposal_disagreement_rate"],
            )
            baseline = summarize(
                run_baseline(frames, failure_rate=config["environment_failure_rate"])
            )
            treatment = summarize(
                run_treatment(frames, failure_rate=config["environment_failure_rate"])
            )
            rows.append(
                {
                    "seed": seed,
                    "scale": scale,
                    "baseline": baseline,
                    "treatment": treatment,
                    "delta_treatment_minus_baseline": {
                        metric: treatment[metric] - baseline[metric]
                        for metric in (
                            "cross_channel_contradiction_rate",
                            "intent_action_divergence_rate",
                            "unsupported_success_claim_rate",
                            "task_success_rate",
                        )
                    },
                }
            )

    return {
        "experiment": config["experiment"],
        "phase": "instrumentation-validation",
        "scientific_claim_allowed": False,
        "config": config,
        "paired_runs": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="experiments/piano_society/config.json",
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    result = run_experiment(_load_config(args.config))
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
