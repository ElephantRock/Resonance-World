"""Independent offline G1 calibration and physical-reservation reconciliation.

Recomputes locked prompts, their complete Z.AI request-body SHA256 digests,
the complete 8-call ITT-style formatting denominator and every stage counter.
The ledger is self-authored and proves NEITHER actual network sends NOR costs.
No provider access, credentials, model calls, or live-run authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .c3r_g1_multischema import ARMS, FAMILIES
from .c3r_g1_multischema_calibration import (
    LOGICAL_BUDGET,
    STATES,
    CalibrationRunner,
)

_RECORD_FIELDS = frozenset({
    "stage", "family", "arm", "task_id", "status", "answer_accepted",
    "reported_completion_tokens", "reported_reasoning_tokens", "finish_reason",
})
_SEND_FIELDS = frozenset({
    "ordinal", "request_digest", "http_status", "failure_class",
})
_FAIL_CLASSES = frozenset({"HttpNon200", "EmptyFinalOutputLengthCap"})


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


def _int(value: object, *, lower: int = 0, upper: int | None = None) -> bool:
    return type(value) is int and value >= lower and (
        upper is None or value <= upper
    )


def _request_digest(
    prompt: str, *, model: str, max_tokens: int,
) -> str:
    params: dict[str, object] = {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0, "max_tokens": max_tokens, "stream": False,
    }
    if model in ("glm-5.3", "glm-5.3-flash"):
        params["thinking"] = {"type": "enabled"}
        params["reasoning_effort"] = "low"
    return _hash(params)


def _forbidden(value: object) -> bool:
    banned = frozenset({
        "api_key", "authorization", "secret", "private_seed",
        "prompt", "prompt_text", "raw_response", "raw_content",
        "reasoning_content", "assistant_content", "response_body",
    })
    if isinstance(value, dict):
        return any(key in banned or _forbidden(v) for key, v in value.items())
    if isinstance(value, list):
        return any(_forbidden(v) for v in value)
    return False


@dataclass(frozen=True, slots=True)
class CalibrationAudit:
    verdict: str
    issues: tuple[str, ...]
    prescribed: int
    reserved: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-calibration-transport-audit-v0.1",
            "verdict": self.verdict,
            "issues": list(self.issues),
            "prescribed_logical_calls": self.prescribed,
            "self_reported_physical_reservations": self.reserved,
            "physical_sends_authenticated": False,
            "billing_authenticated": False,
            "independent_evaluator_attested": False,
            "authorizes_provider_execution": False,
            "authorizes_scientific_study": False,
            "scientific_acceptance": False,
        }


def audit_calibration_transport(
    report: object, ledger: object, *,
    expected_model: str = "glm-5.3",
    expected_route: str = "coding",
    max_tokens: int = 512,
) -> CalibrationAudit:
    issues: list[str] = []
    if (not isinstance(expected_model, str) or not expected_model.strip()
            or expected_route not in ("standard", "coding")
            or not _int(max_tokens, lower=1, upper=512)):
        raise ValueError("reviewed expected model, route and budget required")
    if not isinstance(report, dict) or not isinstance(ledger, dict):
        return CalibrationAudit("rejected", ("missing_report_or_ledger",), 8, 0)
    if _forbidden(report) or _forbidden(ledger):
        issues.append("raw_or_private_material")
    plan = CalibrationRunner(expected_model).plan
    expected_plan_digest = _hash([
        {
            "stage": p.stage, "family": p.family, "arm": p.arm,
            "task": p.task.public_tuple(),
            "prompt_sha256": hashlib.sha256(p.prompt().encode()).hexdigest(),
        } for p in plan
    ])
    if report.get("schema") != "c3r-g1-multischema-calibration-v0.1":
        issues.append("report_schema_invalid")
    if report.get("classification") != (
        "technical_prompt_output_yield_only_no_G1_inference"
    ):
        issues.append("scientific_scope_invalid")
    if report.get("expected_model_id") != expected_model:
        issues.append("model_identity_invalid")
    if report.get("public_plan_digest") != expected_plan_digest:
        issues.append("public_plan_lock_invalid")
    if report.get("prescribed_logical_calls") != LOGICAL_BUDGET:
        issues.append("logical_denominator_invalid")
    for field in ("transport_records_not_authenticated",):
        if report.get(field) is not True:
            issues.append(f"{field}_invalid")
    for field in ("provider_sends_verified", "provider_billing_verified",
                  "scientific_acceptance"):
        if report.get(field) is not False:
            issues.append(f"{field}_must_remain_false")

    rows = report.get("attempt_records")
    if not isinstance(rows, list) or len(rows) != LOGICAL_BUDGET:
        return CalibrationAudit(
            "rejected", (*dict.fromkeys([*issues, "attempt_denominator_invalid"]),),
            LOGICAL_BUDGET, 0,
        )
    normalized: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        target = plan[i]
        if not isinstance(row, dict) or set(row) != _RECORD_FIELDS:
            issues.append("malformed_attempt_record")
            continue
        if any(row.get(key) != value for key, value in (
            ("stage", target.stage), ("family", target.family),
            ("arm", target.arm), ("task_id", target.task.task_id),
        )):
            issues.append("attempt_identity_or_order_mismatch")
        state = row["status"]
        if state not in STATES or type(row["answer_accepted"]) is not bool:
            issues.append("invalid_attempt_status")
            continue
        if row["answer_accepted"] is not (state == "accepted"):
            issues.append("accepted_status_disagreement")
        for field in ("reported_completion_tokens", "reported_reasoning_tokens"):
            if row[field] is not None and not _int(row[field]):
                issues.append("reported_token_usage_invalid")
        if row["finish_reason"] is not None and (
            type(row["finish_reason"]) is not str
            or row["finish_reason"] not in (
                "stop", "length", "tool_calls", "content_filter", "other",
            )
        ):
            issues.append("finish_reason_invalid")
        if state == "accepted" and row["finish_reason"] != "stop":
            issues.append("accepted_without_normal_termination")
        if state == "unfinished_output" and row["finish_reason"] == "stop":
            issues.append("unfinished_has_normal_termination")
        if state == "not_sent_after_failure" and any(
            row[k] is not None for k in (
                "reported_completion_tokens", "reported_reasoning_tokens",
                "finish_reason",
            )
        ):
            issues.append("unsent_has_provider_metadata")
        normalized.append(row)
    if len(normalized) != LOGICAL_BUDGET:
        issues.append("some_attempt_records_not_parseable")

    stops = [i for i, row in enumerate(rows) if isinstance(row, dict)
             and row.get("status") not in ("accepted", "not_sent_after_failure")]
    if stops:
        first = stops[0]
        if any(
            not isinstance(row, dict)
            or row.get("status") != "not_sent_after_failure"
            for row in rows[first + 1:]
        ):
            issues.append("physical_attempt_after_terminal_failure")
        if any(
            not isinstance(row, dict) or row.get("status") != "accepted"
            for row in rows[:first]
        ):
            issues.append("nonaccepted_before_terminal_failure")
        attempted = first + 1
    else:
        attempted = LOGICAL_BUDGET
        if any(
            not isinstance(row, dict) or row.get("status") != "accepted"
            for row in rows
        ):
            issues.append("unsent_without_prior_failure")

    if len(normalized) == LOGICAL_BUDGET:
        accepted = sum(row["status"] == "accepted" for row in normalized)
        dev = sum(
            row["stage"] == "development" and row["answer_accepted"]
            for row in normalized
        )
        triplets = sum(
            all(
                any(row["stage"] == "qualification" and
                    row["family"] == fam and row["arm"] == arm
                    and row["answer_accepted"] for row in normalized)
                for arm in ARMS
            ) for fam in FAMILIES
        )
        families = {
            fam: {
                "prescribed": sum(row["family"] == fam for row in normalized),
                "parseable": sum(
                    row["family"] == fam and row["answer_accepted"]
                    for row in normalized
                ),
                "qualification_by_arm": {
                    arm: sum(
                        row["stage"] == "qualification" and row["family"] == fam
                        and row["arm"] == arm and row["answer_accepted"]
                        for row in normalized
                    ) for arm in ARMS
                },
            } for fam in FAMILIES
        }
        totals = {
            "answered_calls": accepted,
            "answer_yield": accepted / LOGICAL_BUDGET,
            "development_parseable": dev,
            "development_prescribed": 2,
            "qualification_complete_triplets": triplets,
            "qualification_triplets_prescribed": 2,
            "per_family": families,
        }
        if any(report.get(key) != value for key, value in totals.items()):
            issues.append("aggregate_or_family_count_mismatch")
        if report.get("technical_yield_gate") != {
            "requires_all_eight": True,
            "requires_two_complete_triplets": True,
            "passed": accepted == 8 and triplets == 2,
            "authorizes_scientific_study": False,
            "authorizes_provider_sends": False,
        }:
            issues.append("technical_gate_invalid")

    if (ledger.get("schema") != "c3r-physical-send-ledger-v0.1"
            or ledger.get("maximum") != 8):
        issues.append("physical_ledger_contract_invalid")
    entries = ledger.get("entries")
    reserved = ledger.get("reserved")
    if (not isinstance(entries, list) or not _int(reserved, upper=8)
            or len(entries) != reserved):
        return CalibrationAudit(
            "rejected", tuple(dict.fromkeys([*issues, "send_ledger_shape_invalid"])),
            LOGICAL_BUDGET, 0,
        )
    if reserved != attempted:
        # An exception may occur before reservation; only a single terminal
        # adapter_exception at the immediately following row can be unreserved.
        permitted = (
            bool(stops) and stops[0] == reserved
            and rows[stops[0]].get("status") == "adapter_exception"
            and attempted == reserved + 1
        )
        if not permitted:
            issues.append("physical_send_count_vs_attempt_mismatch")
    for ordinal, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or set(entry) != _SEND_FIELDS:
            issues.append("malformed_send_entry")
            continue
        if entry["ordinal"] != ordinal:
            issues.append("send_sequence_invalid")
        if entry["request_digest"] != _request_digest(
            plan[ordinal - 1].prompt(), model=expected_model,
            max_tokens=max_tokens,
        ):
            issues.append("provider_request_body_mismatch")
        status = entry["http_status"]
        failure = entry["failure_class"]
        if status is not None and not _int(status, lower=100, upper=599):
            issues.append("send_http_status_invalid")
        if not (failure is None or isinstance(failure, str)
                and 0 < len(failure) <= 64):
            issues.append("send_failure_class_invalid")
        if failure == "reserved":
            issues.append("incomplete_pre_send_reservation")
        row_state = rows[ordinal - 1].get("status")
        if row_state in ("accepted", "invalid_format",
                         "unfinished_output", "wrong_model", "invalid_completion"):
            if status != 200 or failure not in (None, "EmptyFinalOutputLengthCap"):
                issues.append("model_reply_without_successful_http")
            if failure == "EmptyFinalOutputLengthCap":
                if (ordinal != reserved or row_state == "accepted"
                        or rows[ordinal - 1].get("finish_reason") != "length"
                        and rows[ordinal - 1].get("reported_completion_tokens")
                        != max_tokens):
                    issues.append("invalid_exhaustion_circuit_stop")
        elif row_state == "adapter_exception":
            if failure is None or failure == "reserved":
                issues.append("adapter_failure_without_terminal_ledger_failure")
            if ordinal != reserved:
                issues.append("send_continued_after_adapter_failure")
        else:
            issues.append("physical_send_assigned_to_unsent_row")
    # A terminal malformed answer with a successful HTTP 200 still counts as
    # an attempted send; a reserved request never counts as evidence of a
    # verified provider dispatch or independently reconciled billing.
    return CalibrationAudit(
        "rejected" if issues else "structurally_consistent_unattested",
        tuple(dict.fromkeys(issues)), LOGICAL_BUDGET, reserved,
    )



def _read_bounded_json(path: Path, *, maximum: int) -> object:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("missing, symlinked or oversized calibration artifact")
    data = path.read_bytes()
    if len(data) > maximum:
        raise ValueError("calibration artifact too large")
    return json.loads(data)


def main(argv: list[str] | None = None) -> int:
    """Validate offline artifacts only. Never opens a provider connection."""
    parser = argparse.ArgumentParser(
        description="Check G1 calibration reports against reserved request hashes"
    )
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--route", choices=("coding", "standard"), required=True)
    parser.add_argument("--max-tokens", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        report = _read_bounded_json(args.report, maximum=128 * 1024)
        ledger = _read_bounded_json(args.ledger, maximum=16 * 1024)
        result = audit_calibration_transport(
            report, ledger, expected_model=args.model,
            expected_route=args.route, max_tokens=args.max_tokens,
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        result = CalibrationAudit("rejected", ("invalid_or_unavailable_input",), 8, 0)
    print(json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if result.verdict == "structurally_consistent_unattested" else 2


if __name__ == "__main__":
    raise SystemExit(main())
