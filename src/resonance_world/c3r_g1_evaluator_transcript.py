"""Independent offline verifier of complete, signed G1 evaluator transcripts.

The verifier needs ONLY an out-of-band pinned public signing key and the
public prospective cohort. Signature validity does NOT imply that a trusted
evaluator owned the key or that private outcome labels were scientifically
correct. Never use a private key or provider credential in this module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .c3r_g1_evaluator_receipts import ReceiptVerifier
from .c3r_g1_multischema import ARMS, STATUSES, PublicCohort

FIELDS = frozenset({
    "unit_id", "arm", "stage", "task_id", "family", "context",
    "status", "choice", "success",
})


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class TranscriptAudit:
    status: str
    errors: tuple[str, ...]
    signed_messages: int
    signed_attempts: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-signed-transcript-audit-v0.1",
            "status": self.status,
            "errors": list(self.errors),
            "signed_messages": self.signed_messages,
            "signed_attempts": self.signed_attempts,
            "signature_chain_verified": self.status == "signed_structurally_consistent",
            "evaluator_independence_attested": False,
            "private_grade_correctness_verified": False,
            "provider_sends_verified": False,
            "scientific_acceptance": False,
        }


def audit_signed_transcript(
    messages: object, cohort: PublicCohort,
    *, public_key_hex: str, expected_run_id: str,
) -> TranscriptAudit:
    dev_expected = cohort.design.units * 2 * cohort.design.development_per_family
    qual_expected = cohort.design.heldout_triplets * 3
    count = dev_expected + qual_expected + 2
    if not isinstance(messages, list) or len(messages) != count:
        return TranscriptAudit(
            "rejected_incomplete_or_invalid", ("signed_denominator_mismatch",), 0, 0
        )

    verifier = ReceiptVerifier(public_key_hex, expected_run_id=expected_run_id)
    signed_payloads: list[dict[str, object]] = []
    try:
        for message in messages:
            signed_payloads.append(verifier.verify_next(message))
    except (ValueError, TypeError, KeyError):
        return TranscriptAudit(
            "rejected_incomplete_or_invalid", ("signature_or_chain_invalid",),
            len(signed_payloads), 0,
        )

    errors: list[str] = []
    ready = signed_payloads[0]
    final = signed_payloads[-1]
    if (set(ready) != {
        "schema", "phase", "public_cohort_digest", "target_commitment",
        "development_expected", "qualification_expected", "independently_attested",
    } or ready.get("schema") != "c3r-g1-evaluator-v0.1"
            or ready.get("phase") != "accept_development"
            or ready.get("public_cohort_digest") != cohort.digest
            or ready.get("development_expected") != dev_expected
            or ready.get("qualification_expected") != qual_expected
            or ready.get("independently_attested") is not False):
        errors.append("ready_cohort_or_contract_mismatch")
    commitment = ready.get("target_commitment")
    if not isinstance(commitment, str) or len(commitment) != 64:
        errors.append("invalid_commitment")

    expected_dev: dict[str, tuple[str, str, str]] = {}
    expected_qual: dict[str, tuple[str, str, str]] = {}
    prescribed: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    for unit in cohort.units:
        for group in unit.families:
            for task in group.development:
                expected_dev[task.task_id] = (unit.unit_id, group.family, group.context)
                prescribed[unit.unit_id, "learned", "development", task.task_id] = (
                    group.family, group.context
                )
            for task in group.qualification:
                expected_qual[task.task_id] = (
                    unit.unit_id, group.family, group.context
                )
                for arm in ARMS:
                    prescribed[unit.unit_id, arm, "qualification", task.task_id] = (
                        group.family, group.context
                    )

    dev_receipts: dict[str, tuple[bool, bool | None]] = {}
    for index, payload in enumerate(signed_payloads[1:1 + dev_expected], 1):
        key = payload.get("task_id")
        accepted = payload.get("accepted")
        grade = payload.get("grade")
        if (set(payload) != {
            "schema", "phase", "task_id", "grade", "accepted",
            "development_received",
        } or payload.get("schema") != "c3r-g1-evaluator-v0.1"
                or payload.get("phase") != "development_feedback"
                or payload.get("development_received") != index
                or not isinstance(key, str) or key not in expected_dev
                or key in dev_receipts
                or type(accepted) is not bool
                or (accepted and type(grade) is not bool)
                or (not accepted and grade is not None)):
            errors.append("invalid_development_receipt")
            continue
        dev_receipts[key] = (accepted, grade)
    if len(dev_receipts) != dev_expected:
        errors.append("missing_development_receipts")

    qualification_seen: dict[str, int] = {}
    for index, payload in enumerate(
        signed_payloads[1 + dev_expected:-1], 1
    ):
        key = payload.get("task_id")
        if (set(payload) != {
            "schema", "phase", "task_id", "qualification_received"
        } or payload.get("schema") != "c3r-g1-evaluator-v0.1"
                or payload.get("phase") != "qualification_sealed"
                or payload.get("qualification_received") != index
                or not isinstance(key, str) or key not in expected_qual):
            errors.append("invalid_or_leaked_qualification_receipt")
            continue
        qualification_seen[key] = qualification_seen.get(key, 0) + 1
    if len(qualification_seen) != len(expected_qual) or any(
        value != len(ARMS) for value in qualification_seen.values()
    ):
        errors.append("qualification_triplet_coverage_mismatch")

    records = final.get("records")
    if (set(final) != {
        "schema", "status", "public_cohort_digest", "target_commitment",
        "development_attempts", "qualification_attempts",
        "records_sha256", "records", "independently_attested",
        "provider_sends_verified", "scientific_acceptance",
    } or final.get("schema") != "c3r-g1-evaluator-final-v0.1"
            or final.get("status") != "local_process_fixture_no_scientific_acceptance"
            or final.get("public_cohort_digest") != cohort.digest
            or final.get("target_commitment") != commitment
            or final.get("development_attempts") != dev_expected
            or final.get("qualification_attempts") != qual_expected
            or final.get("independently_attested") is not False
            or final.get("provider_sends_verified") is not False
            or final.get("scientific_acceptance") is not False):
        errors.append("invalid_signed_final_contract")

    if not isinstance(records, list) or len(records) != len(prescribed):
        errors.append("final_record_denominator_mismatch")
        records = []
    if final.get("records_sha256") != _hash(records):
        errors.append("final_record_digest_mismatch")

    observed: set[tuple[str, str, str, str]] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != FIELDS:
            errors.append("malformed_signed_record")
            continue
        fields = ("unit_id", "arm", "stage", "task_id")
        if any(type(record.get(name)) is not str for name in fields):
            errors.append("invalid_record_identity")
            continue
        key = tuple(record[name] for name in fields)
        if key not in prescribed or key in observed:
            errors.append("unregistered_or_repeated_signed_attempt")
            continue
        observed.add(key)
        if (record.get("family"), record.get("context")) != prescribed[key]:
            errors.append("signed_record_family_mismatch")
        status = record.get("status")
        accepted = status == "accepted"
        if (status not in STATUSES or type(record.get("success")) is not bool
                or (accepted and record.get("choice") not in ("A", "B"))
                or (not accepted and (
                    record.get("choice") is not None or record["success"]
                ))):
            errors.append("invalid_signed_outcome")
        if key[2] == "development":
            feedback = dev_receipts.get(key[3])
            if feedback is None or feedback != (
                accepted, record["success"] if accepted else None
            ):
                errors.append("development_feedback_not_bound_to_final")
    if observed != set(prescribed):
        errors.append("signed_record_membership_incomplete")

    return TranscriptAudit(
        "rejected_incomplete_or_invalid" if errors else "signed_structurally_consistent",
        tuple(dict.fromkeys(errors)), len(signed_payloads), len(observed),
    )
