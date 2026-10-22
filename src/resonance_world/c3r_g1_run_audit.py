"""Offline-only structural audit for a C3R G1 technical smoke artifact.

A passing audit validates the *internal consistency of an untrusted report*.
It cannot establish GitHub provenance, an independent evaluator, billing truth,
provider identity, source acquisition, statistical significance, or G2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
VALID_STAGES = ("development", "qualification_learned", "qualification_fresh")
FAILURE_CLASSES = (
    "invalid_format",
    "adapter_exception",
    "invalid_adapter_result",
    "reported_send_cap_exceeded",
)
ALLOWED_STATUSES = (*FAILURE_CLASSES, "accepted")
FORBIDDEN_FIELDS = frozenset(
    {
        "raw_response_text", "raw_provider_body", "raw_content",
        "prompt", "prompt_text", "api_key", "secret",
        "authorization", "assistant_content", "response_body",
    }
)


def _integer(value: object, *, low: int = 0, high: int | None = None) -> bool:
    return type(value) is int and value >= low and (high is None or value <= high)


def _digest(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def _contains_forbidden_fields(value: object) -> bool:
    if isinstance(value, dict):
        if any(key in FORBIDDEN_FIELDS for key in value):
            return True
        return any(_contains_forbidden_fields(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_fields(item) for item in value)
    return False


@dataclass(frozen=True, slots=True)
class TechnicalSmokeAudit:
    """Structural verdict only; not proof that any actual provider call happened."""

    status: str
    issues: tuple[str, ...]
    reserved_sends: int | None
    accepted_actions: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-smoke-audit-v0.1",
            "status": self.status,
            "issues": list(self.issues),
            "reserved_sends_in_report": self.reserved_sends,
            "accepted_actions_in_report": self.accepted_actions,
            "provider_execution_verified": False,
            "independently_attested": False,
            "scientific_acceptance": False,
        }


def audit_technical_smoke(
    artifact: object,
    *,
    expected_cohort_digest: str,
    expected_route: str = "coding",
    expected_model: str = "glm-5.3",
) -> TechnicalSmokeAudit:
    """Audit a previously saved JSON object, with no network or credentials."""
    issues: list[str] = []
    reserved: int | None = None
    accepted_total: int | None = None
    if not _digest(expected_cohort_digest):
        raise ValueError("expected cohort digest must be lowercase SHA256")
    if expected_route not in ("coding", "standard") or not expected_model:
        raise ValueError("expected route and model must be explicit")
    if not isinstance(artifact, dict):
        return TechnicalSmokeAudit("invalid_artifact", ("top_level_not_object",), None, None)
    if _contains_forbidden_fields(artifact):
        issues.append("raw_or_secret_field_present")

    if artifact.get("schema") != "c3r-live-technical-qualification-v0.1":
        issues.append("unexpected_schema")
    if artifact.get("status") != "technical_smoke_not_scientific_evidence":
        issues.append("unexpected_status")
    if artifact.get("scientific_acceptance") is not False:
        issues.append("scientific_acceptance_must_be_false")
    if artifact.get("model") != expected_model:
        issues.append("model_mismatch")
    if artifact.get("route") != expected_route:
        issues.append("route_mismatch")
    if artifact.get("cohort_digest") != expected_cohort_digest:
        issues.append("cohort_mismatch")

    report = artifact.get("report")
    if not isinstance(report, dict):
        issues.append("missing_model_report")
        report = {}
    if report.get("schema") != "c3r-g1-model-boundary-construction-v0.1":
        issues.append("model_report_schema_mismatch")
    if report.get("status") != "construction_only_not_scientific_evidence":
        issues.append("model_report_status_mismatch")
    if report.get("port_type") != "injected_unverified_adapter":
        issues.append("model_port_provenance_unattested")
    if report.get("cohort_digest") != expected_cohort_digest:
        issues.append("model_report_cohort_mismatch")

    stage_expected = {"development": 4, "qualification_learned": 2,
                      "qualification_fresh": 2}
    stage_accepted: dict[str, int] = {}
    counts_ok = True
    for stage in VALID_STAGES:
        data = report.get(stage)
        if not isinstance(data, dict):
            issues.append(f"{stage}_missing")
            counts_ok = False
            continue
        attempts = data.get("attempts")
        accepted = data.get("accepted")
        successes = data.get("successes")
        failures = data.get("failures_by_status")
        if not _integer(attempts) or attempts != stage_expected[stage]:
            issues.append(f"{stage}_attempt_denominator_invalid")
            counts_ok = False
            continue
        if not _integer(accepted, high=attempts):
            issues.append(f"{stage}_accepted_count_invalid")
            counts_ok = False
            continue
        if not _integer(successes, high=accepted):
            issues.append(f"{stage}_success_count_invalid")
            counts_ok = False
            continue
        if not isinstance(failures, dict) or not set(failures) <= set(FAILURE_CLASSES):
            issues.append(f"{stage}_failures_invalid")
            counts_ok = False
            continue
        if any(not _integer(value) for value in failures.values()):
            issues.append(f"{stage}_failure_count_invalid")
            counts_ok = False
            continue
        if accepted + sum(failures.values()) != attempts:
            issues.append(f"{stage}_accounting_mismatch")
            counts_ok = False
            continue
        stage_accepted[stage] = accepted
        for key in ("physical_sends_reported", "prompt_tokens_reported",
                    "completion_tokens_reported"):
            if not _integer(data.get(key)):
                issues.append(f"{stage}_{key}_invalid")
    if counts_ok and len(stage_accepted) == len(VALID_STAGES):
        accepted_total = sum(stage_accepted.values())
    if report.get("source_evidence_count") != stage_accepted.get("development"):
        issues.append("source_evidence_count_mismatch")

    ledger = artifact.get("send_ledger")
    entries: Any = None
    if not isinstance(ledger, dict):
        issues.append("missing_send_ledger")
    else:
        entries = ledger.get("entries")
        reserved = ledger.get("reserved") if _integer(ledger.get("reserved")) else None
        if ledger.get("schema") != "c3r-physical-send-ledger-v0.1":
            issues.append("ledger_schema_mismatch")
        if ledger.get("maximum") != 8 or reserved != 8:
            issues.append("send_reservation_count_mismatch")
        if not isinstance(entries, list) or len(entries) != 8:
            issues.append("ledger_entries_count_mismatch")
        else:
            for index, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    issues.append("malformed_ledger_entry")
                    continue
                if entry.get("ordinal") != index or not _digest(entry.get("request_digest")):
                    issues.append("ledger_sequence_or_digest_invalid")
                code = entry.get("http_status")
                failure = entry.get("failure_class")
                if code is not None and not _integer(code, low=100, high=599):
                    issues.append("ledger_http_status_invalid")
                if failure == "reserved":
                    issues.append("unclosed_send_reservation")
                if failure is not None and (
                    not isinstance(failure, str) or len(failure) > 64
                ):
                    issues.append("ledger_failure_class_invalid")

    observations = report.get("bounded_observations")
    if not isinstance(observations, list) or len(observations) != 8:
        issues.append("observation_count_mismatch")
    else:
        actual_stages = [record.get("stage") if isinstance(record, dict) else None
                         for record in observations]
        if actual_stages != ["development"] * 4 + ["qualification"] * 4:
            issues.append("observation_stage_order_invalid")
        if any(
            not isinstance(record, dict)
            or record.get("status") not in ALLOWED_STATUSES
            or record.get("model_id") not in (expected_model, None)
            or (record.get("output_sha256") is not None
                and not _digest(record["output_sha256"]))
            for record in observations
        ):
            issues.append("observation_content_invalid")
        if all(isinstance(record, dict) for record in observations):
            stage_rows = {
                "development": observations[:4],
                "qualification_learned": observations[4:6],
                "qualification_fresh": observations[6:],
            }
            for stage in VALID_STAGES:
                if stage in stage_accepted and sum(
                    row.get("status") == "accepted" for row in stage_rows[stage]
                ) != stage_accepted[stage]:
                    issues.append(f"{stage}_observation_count_mismatch")
    # The summary groups qualifications by arm; physical sends were actually
    # interleaved learned/fresh within each heldout task. Reconstruct order.
    if isinstance(entries, list) and len(entries) == 8 and isinstance(
        observations, list
    ) and len(observations) == 8:
        ledger_order = (0, 1, 2, 3, 4, 6, 5, 7)
        for ordinal, source_index in enumerate(ledger_order):
            entry = entries[ordinal]
            observation = observations[source_index]
            if not isinstance(entry, dict) or not isinstance(observation, dict):
                continue
            if observation.get("status") in ("accepted", "invalid_format"):
                if (entry.get("http_status") != 200
                        or entry.get("failure_class") is not None):
                    issues.append("accepted_or_parsed_without_http_success")
                if not _digest(observation.get("output_sha256")):
                    issues.append("parsed_output_digest_missing")

    paired = report.get("paired_analyzable")
    if not _integer(paired, high=2):
        issues.append("paired_analyzable_invalid")
    elif len(stage_accepted) == 3 and paired > min(
        stage_accepted["qualification_learned"],
        stage_accepted["qualification_fresh"],
    ):
        issues.append("paired_analyzable_exceeds_accepted")

    if issues:
        return TechnicalSmokeAudit(
            "rejected_inconsistent_artifact",
            tuple(dict.fromkeys(issues)),
            reserved,
            accepted_total,
        )
    return TechnicalSmokeAudit(
        "structurally_consistent_unattested",
        (),
        reserved,
        accepted_total,
    )
