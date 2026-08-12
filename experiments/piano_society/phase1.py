"""Phase-1 validator and mechanical scorer for Field-exported PIANO records."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_FIXTURE_SCHEMA = "resonance-field-piano-fixture-v0.1"
_RECORD_SCHEMA = "resonance-field-piano-step-v0.1"


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _records(
    payload: Mapping[str, Any], *, expected_arm: str
) -> list[Mapping[str, Any]]:
    if payload.get("schema") != _FIXTURE_SCHEMA:
        raise ValueError("unsupported Field fixture schema")
    if payload.get("arm") != expected_arm:
        raise ValueError(f"expected {expected_arm} arm")
    if payload.get("scientific_claim_allowed") is not False:
        raise ValueError("Phase-1 contract fixture must remain non-scientific")
    raw = payload.get("records")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise ValueError("records must be a non-empty sequence")

    records: list[Mapping[str, Any]] = []
    for index, value in enumerate(raw):
        record = _mapping(value, f"records[{index}]")
        if record.get("schema") != _RECORD_SCHEMA:
            raise ValueError(f"records[{index}] has unsupported schema")
        if not isinstance(record.get("agent_id"), str):
            raise ValueError(f"records[{index}].agent_id must be a string")
        if not isinstance(record.get("occurred_at"), str):
            raise ValueError(f"records[{index}].occurred_at must be a string")
        if not isinstance(record.get("action"), str):
            raise ValueError(f"records[{index}].action must be a string")
        if not isinstance(record.get("speech_claims_success"), bool):
            raise ValueError(f"records[{index}].speech_claims_success must be boolean")
        acknowledgement = _mapping(record.get("acknowledgement"), "acknowledgement")
        if not isinstance(acknowledgement.get("grounded_success"), bool):
            raise ValueError("acknowledgement.grounded_success must be boolean")
        expectation_met = acknowledgement.get("expectation_met")
        if expectation_met is not None and not isinstance(expectation_met, bool):
            raise ValueError("acknowledgement.expectation_met must be boolean or null")
        records.append(record)
    return records


def _pair_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return str(record["agent_id"]), str(record["occurred_at"])


def score_records(records: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    if not records:
        raise ValueError("records must not be empty")

    observations = len(records)
    speech_labeled = [record for record in records if record.get("speech_action") is not None]
    intent_labeled = [
        record for record in records if record.get("intended_action") is not None
    ]
    expected = [
        record
        for record in records
        if _mapping(record["acknowledgement"], "acknowledgement").get("expectation_met")
        is not None
    ]

    contradictions = sum(
        record.get("speech_action") != record.get("action") for record in speech_labeled
    )
    divergences = sum(
        record.get("intended_action") != record.get("action") for record in intent_labeled
    )
    unsupported_success = sum(
        bool(record["speech_claims_success"])
        and not bool(
            _mapping(record["acknowledgement"], "acknowledgement")["grounded_success"]
        )
        for record in records
    )
    expectation_failures = sum(
        _mapping(record["acknowledgement"], "acknowledgement")["expectation_met"] is False
        for record in expected
    )
    execution_successes = sum(
        bool(_mapping(record["acknowledgement"], "acknowledgement")["grounded_success"])
        for record in records
    )

    return {
        "observations": observations,
        "cross_channel_contradiction_rate": (
            contradictions / len(speech_labeled) if speech_labeled else 0.0
        ),
        "intent_action_divergence_rate": (
            divergences / len(intent_labeled) if intent_labeled else 0.0
        ),
        "unsupported_success_claim_rate": unsupported_success / observations,
        "expectation_failure_rate": (
            expectation_failures / len(expected) if expected else 0.0
        ),
        "execution_success_rate": execution_successes / observations,
    }


def run_pair(
    control_payload: Mapping[str, Any],
    treatment_payload: Mapping[str, Any],
    *,
    field_sha: str,
) -> dict[str, Any]:
    if (
        len(field_sha) != 40
        or any(character not in "0123456789abcdef" for character in field_sha)
    ):
        raise ValueError("field_sha must be a lowercase 40-character Git SHA")

    control = _records(control_payload, expected_arm="control")
    treatment = _records(treatment_payload, expected_arm="treatment")
    if [
        _pair_key(record) for record in control
    ] != [
        _pair_key(record) for record in treatment
    ]:
        raise ValueError("control and treatment records are not paired by agent/time")

    control_score = score_records(control)
    treatment_score = score_records(treatment)
    metric_names = (
        "cross_channel_contradiction_rate",
        "intent_action_divergence_rate",
        "unsupported_success_claim_rate",
        "expectation_failure_rate",
        "execution_success_rate",
    )
    return {
        "experiment": "piano-society-runtime-v0-phase1-contract",
        "phase": "live-contract-smoke",
        "scientific_claim_allowed": False,
        "field_revision": field_sha,
        "record_schema": _RECORD_SCHEMA,
        "control": control_score,
        "treatment": treatment_score,
        "delta_treatment_minus_control": {
            metric: treatment_score[metric] - control_score[metric]
            for metric in metric_names
        },
    }


def _load(path: str | Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", required=True)
    parser.add_argument("--treatment", required=True)
    parser.add_argument("--field-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = run_pair(
        _load(args.control),
        _load(args.treatment),
        field_sha=args.field_sha,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
