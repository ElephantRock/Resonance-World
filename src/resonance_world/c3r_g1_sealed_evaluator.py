"""Sealed, evaluator-owned G1 grade protocol; local process prototype only.

This module has NO model adapter or API client. Construct it inside an
evaluator-controlled process with a private 256-bit key, not in an agent port.
An HMAC-derived commitment is not an external signature or attestation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from .c3r_g1_multischema import ARMS, STATUSES, PublicCohort, SchemaTask, apply_choice


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class EvaluatorEnvelope:
    """Explicitly bounded machine-readable return value, not an attestation."""

    payload: dict[str, object]

    def to_json(self) -> str:
        return _canonical(self.payload).decode("utf-8")


class SealedEvaluator:
    """Accept prescribed attempts, release holdout grades only after closure."""

    def __init__(self, cohort: PublicCohort, *, private_key: bytes) -> None:
        if not isinstance(private_key, bytes) or len(private_key) != 32:
            raise ValueError("evaluator requires a private 32-byte secret")
        self.cohort = cohort
        self._private_key = private_key
        self._expected: dict[tuple[str, str, str, str], SchemaTask] = {}
        targets: dict[tuple[str, str], str] = {}
        for unit in cohort.units:
            for family in unit.families:
                target_key = (unit.unit_id, family.context)
                digest = hmac.digest(
                    private_key, _canonical(["target", *target_key]), "sha256"
                )
                targets[target_key] = "A" if digest[0] % 2 == 0 else "B"
                for task in family.development:
                    self._expected[
                        (unit.unit_id, "learned", "development", task.task_id)
                    ] = task
                for task in family.qualification:
                    for arm in ARMS:
                        self._expected[
                            (unit.unit_id, arm, "qualification", task.task_id)
                        ] = task
        self._targets = targets
        self._development_expected = (
            cohort.design.units * 2 * cohort.design.development_per_family
        )
        self._qualification_expected = (
            cohort.design.units * 2 * cohort.design.qualification_per_family * 3
        )
        self._records: dict[tuple[str, str, str, str], dict[str, object]] = {}
        self._development_seen = 0
        self._qualification_seen = 0
        self._closed = False
        # Private-key-derived nonce prevents public brute-force of a simple
        # low-entropy public seed. It is NOT a third-party trusted timestamp.
        nonce = hmac.digest(private_key, b"c3r-g1-target-commit-v1", "sha256").hex()
        self._commitment = _hash({
            "cohort": cohort.digest,
            "target_mapping": [
                [unit_id, ctx, choice]
                for (unit_id, ctx), choice in sorted(targets.items())
            ],
            "private_nonce": nonce,
        })

    def ready(self) -> EvaluatorEnvelope:
        return EvaluatorEnvelope({
            "schema": "c3r-g1-evaluator-v0.1",
            "phase": "accept_development",
            "public_cohort_digest": self.cohort.digest,
            "target_commitment": self._commitment,
            "development_expected": self._development_expected,
            "qualification_expected": self._qualification_expected,
            "independently_attested": False,
        })

    def submit(self, request: Any) -> EvaluatorEnvelope:
        if self._closed:
            raise ValueError("evaluator already finalized")
        if not isinstance(request, dict) or set(request) != {
            "op", "unit_id", "arm", "stage", "task_id", "status", "choice"
        } or request.get("op") != "submit":
            raise ValueError("malformed evaluator request")
        unit_id, arm, stage, task_id = (
            request[field] for field in ("unit_id", "arm", "stage", "task_id")
        )
        if any(type(field) is not str for field in (
            unit_id, arm, stage, task_id
        )):
            raise ValueError("invalid attempt identifiers")
        key = (unit_id, arm, stage, task_id)
        if key not in self._expected:
            raise ValueError("attempt not prescribed in cohort")
        if key in self._records:
            raise ValueError("duplicate attempt")
        status, choice = request["status"], request["choice"]
        if status not in STATUSES or (
            (status == "accepted" and choice not in ("A", "B"))
            or (status != "accepted" and choice is not None)
        ):
            raise ValueError("invalid status/action pairing")
        if stage == "development" and self._qualification_seen:
            raise ValueError("development cannot follow qualification")
        if stage == "qualification" and (
            self._development_seen != self._development_expected
        ):
            raise ValueError("development denominator not sealed")
        task = self._expected[key]
        success = bool(
            status == "accepted"
            and apply_choice(task, choice)
            == apply_choice(task, self._targets[unit_id, task.context])
        )
        attempt = {
            "unit_id": unit_id,
            "arm": arm,
            "stage": stage,
            "task_id": task_id,
            "family": task.family,
            "context": task.context,
            "status": status,
            "choice": choice,
            "success": success,
        }
        self._records[key] = attempt
        if stage == "development":
            self._development_seen += 1
            return EvaluatorEnvelope({
                "schema": "c3r-g1-evaluator-v0.1",
                "phase": "development_feedback",
                "task_id": task_id,
                "grade": success if status == "accepted" else None,
                "accepted": status == "accepted",
                "development_received": self._development_seen,
            })
        self._qualification_seen += 1
        # No qualification grade, target, success count, or grade-derived
        # digest is returned while any holdout result could influence a port.
        return EvaluatorEnvelope({
            "schema": "c3r-g1-evaluator-v0.1",
            "phase": "qualification_sealed",
            "task_id": task_id,
            "qualification_received": self._qualification_seen,
        })

    def finalize(self, request: Any) -> EvaluatorEnvelope:
        if not isinstance(request, dict) or request != {"op": "finalize"}:
            raise ValueError("invalid finalize request")
        if self._closed:
            raise ValueError("finalization is one shot")
        if (self._development_seen != self._development_expected
                or self._qualification_seen != self._qualification_expected
                or len(self._records) != len(self._expected)):
            raise ValueError("prescribed denominator incomplete")
        self._closed = True
        outcomes = [
            self._records[key] for key in sorted(self._records)
        ]
        return EvaluatorEnvelope({
            "schema": "c3r-g1-evaluator-final-v0.1",
            "status": "local_process_fixture_no_scientific_acceptance",
            "public_cohort_digest": self.cohort.digest,
            "target_commitment": self._commitment,
            "development_attempts": self._development_seen,
            "qualification_attempts": self._qualification_seen,
            "records_sha256": _hash(outcomes),
            "records": outcomes,
            "independently_attested": False,
            "provider_sends_verified": False,
            "scientific_acceptance": False,
        })
