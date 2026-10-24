"""Offline tests for C3R provider technical report structural reconciliation."""

from __future__ import annotations

import copy
import json

import pytest

from resonance_world.c3r_g1_model_boundary import ModelCohortLock, ModelG1Runner
from resonance_world.c3r_g1_run_audit import audit_technical_smoke
from resonance_world.c3r_g1_zai_transport import (
    PhysicalSendLedger,
    TransportResponse,
    ZaiStandardModelPort,
)
from resonance_world.c3r_g2_probe import FixtureOracle, make_task


def _artifact() -> tuple[dict[str, object], str]:
    context = "c3r-source-smoke-1"
    cohort = ModelCohortLock(
        tuple(make_task(split="dev", context=context, number=n) for n in range(4)),
        tuple(make_task(split="holdout", context=context, number=n) for n in range(2)),
    )
    ledger = PhysicalSendLedger(8)

    def one_response(url, headers, body, timeout):
        assert url.endswith("/api/coding/paas/v4/chat/completions")
        assert "Bearer fixture" == headers["Authorization"]
        assert 0 < timeout <= 30
        request = json.loads(body)
        assert request["model"] == "glm-5.3"
        return TransportResponse(
            200,
            json.dumps({
                "choices": [{"message": {"content": "B"}}],
                "model": "glm-5.3",
                "usage": {"prompt_tokens": 17, "completion_tokens": 1},
            }).encode(),
        )

    port = ZaiStandardModelPort(
        api_key="fixture", model_id="glm-5.3", ledger=ledger,
        enabled=True, route="coding", transport=one_response,
        max_tokens=512, timeout_seconds=30,
    )
    output = ModelG1Runner(
        oracle=FixtureOracle({context: ("multiply", "add")}),
        cohort=cohort,
    ).execute(owner_id="fixture-source", learned_port=port, fresh_port=port)
    return {
        "schema": "c3r-live-technical-qualification-v0.1",
        "status": "technical_smoke_not_scientific_evidence",
        "cohort_digest": cohort.digest,
        "model": "glm-5.3",
        "route": "coding",
        "report": output.to_dict(),
        "send_ledger": ledger.to_dict(),
        "scientific_acceptance": False,
    }, cohort.digest


def test_consistent_offline_fixture_is_only_structurally_attested() -> None:
    artifact, lock = _artifact()
    audited = audit_technical_smoke(artifact, expected_cohort_digest=lock)
    assert audited.status == "structurally_consistent_unattested"
    assert audited.issues == ()
    assert audited.reserved_sends == 8
    assert audited.accepted_actions == 8
    result = audited.to_dict()
    assert result["provider_execution_verified"] is False
    assert result["independently_attested"] is False
    assert result["scientific_acceptance"] is False
    assert "fixture" not in json.dumps(result)


@pytest.mark.parametrize(
    ("path", "value", "issue"),
    [
        (("cohort_digest",), "0" * 64, "cohort_mismatch"),
        (("route",), "standard", "route_mismatch"),
        (("model",), "different-model", "model_mismatch"),
        (("scientific_acceptance",), True, "scientific_acceptance_must_be_false"),
        (("send_ledger", "reserved"), 7, "ledger_entries_count_mismatch"),
        (("send_ledger", "maximum"), 999, "send_reservation_count_mismatch"),
        (("send_ledger", "entries", 0, "ordinal"), 3, "ledger_sequence_or_digest_invalid"),
        (("send_ledger", "entries", 0, "failure_class"), "reserved",
         "unclosed_send_reservation"),
        (("report", "cohort_digest"), "0" * 64, "model_report_cohort_mismatch"),
        (("report", "development", "attempts"), 3,
         "development_attempt_denominator_invalid"),
        (("report", "development", "accepted"), 9,
         "development_accepted_count_invalid"),
        (("report", "qualification_learned", "successes"), 9,
         "qualification_learned_success_count_invalid"),
        (("report", "paired_analyzable"), 3, "paired_analyzable_invalid"),
        (("report", "source_evidence_count"), 0, "source_evidence_count_mismatch"),
        (("report", "bounded_observations", 0, "status"), "unrecognized",
         "observation_content_invalid"),
        (("report", "bounded_observations", 0, "output_sha256"), "not-a-digest",
         "observation_content_invalid"),
    ],
)
def test_tampered_report_fails_closed(path, value, issue) -> None:
    artifact, lock = _artifact()
    modified = copy.deepcopy(artifact)
    nested = modified
    for segment in path[:-1]:
        nested = nested[segment]
    nested[path[-1]] = value
    report = audit_technical_smoke(modified, expected_cohort_digest=lock)
    assert report.status == "rejected_inconsistent_artifact"
    assert issue in report.issues
    assert not report.to_dict()["provider_execution_verified"]


def test_rejects_missing_and_raw_secret_content() -> None:
    artifact, lock = _artifact()
    artifact["report"]["raw_response_text"] = "SIMULATED PRIVATE RAW OUTPUT"
    artifact["send_ledger"]["api_key"] = "SIMULATED SECRET"
    result = audit_technical_smoke(artifact, expected_cohort_digest=lock)
    assert result.status == "rejected_inconsistent_artifact"
    assert "raw_or_secret_field_present" in result.issues
    summary = json.dumps(result.to_dict())
    assert "SIMULATED SECRET" not in summary
    assert "SIMULATED PRIVATE RAW OUTPUT" not in summary


def test_missing_artifact_or_incomplete_ledger_not_evidence() -> None:
    artifact, lock = _artifact()
    assert audit_technical_smoke({}, expected_cohort_digest=lock).status == (
        "rejected_inconsistent_artifact"
    )
    assert audit_technical_smoke([], expected_cohort_digest=lock).status == (
        "invalid_artifact"
    )
    artifact["send_ledger"]["entries"].pop()
    result = audit_technical_smoke(artifact, expected_cohort_digest=lock)
    assert "ledger_entries_count_mismatch" in result.issues


def test_expected_digest_and_route_must_be_explicit() -> None:
    artifact, lock = _artifact()
    with pytest.raises(ValueError, match="expected cohort"):
        audit_technical_smoke(artifact, expected_cohort_digest="wrong")
    with pytest.raises(ValueError, match="expected route"):
        audit_technical_smoke(
            artifact, expected_cohort_digest=lock, expected_route="anything"
        )


def test_zero_valid_actions_is_not_model_acquisition() -> None:
    artifact, lock = _artifact()
    report = artifact["report"]
    entries = artifact["send_ledger"]["entries"]
    for stage in ("development", "qualification_learned", "qualification_fresh"):
        data = report[stage]
        count = data["attempts"]
        data["accepted"] = 0
        data["successes"] = 0
        data["failures_by_status"] = {"adapter_exception": count}
        data["physical_sends_reported"] = 0
    report["paired_analyzable"] = 0
    report["source_evidence_count"] = 0
    for ordinal, record in enumerate(report["bounded_observations"]):
        record["status"] = "adapter_exception"
        record["model_id"] = None
        record["output_sha256"] = None
        record["error_class"] = (
            "ProviderTransportRejected" if ordinal == 0 else "ProviderCircuitOpen"
        )
    del entries[1:]
    entries[0]["http_status"] = 401
    entries[0]["failure_class"] = "HttpNon200"
    artifact["send_ledger"]["reserved"] = 1
    result = audit_technical_smoke(artifact, expected_cohort_digest=lock)
    assert result.status == "structurally_consistent_unattested"
    assert result.accepted_actions == 0
    assert result.to_dict()["scientific_acceptance"] is False



def test_grader_cannot_accept_a_reply_that_the_transport_says_failed() -> None:
    artifact, lock = _artifact()
    artifact["send_ledger"]["entries"][0]["http_status"] = None
    artifact["send_ledger"]["entries"][0]["failure_class"] = "TimeoutError"
    verdict = audit_technical_smoke(artifact, expected_cohort_digest=lock)
    assert verdict.status == "rejected_inconsistent_artifact"
    assert "accepted_or_parsed_without_http_success" in verdict.issues



def test_completed_send_summary_must_match_accepted_and_invalid_format() -> None:
    artifact, lock = _artifact()
    artifact["report"]["development"]["physical_sends_reported"] = 0
    verdict = audit_technical_smoke(artifact, expected_cohort_digest=lock)
    assert verdict.status == "rejected_inconsistent_artifact"
    assert "development_completed_send_accounting_mismatch" in verdict.issues



def test_provider_401_closes_circuit_without_consuming_other_seven_sends() -> None:
    context = "c3r-source-smoke-1"
    cohort = ModelCohortLock(
        tuple(make_task(split="dev", context=context, number=n) for n in range(4)),
        tuple(make_task(split="holdout", context=context, number=n) for n in range(2)),
    )
    attempted = []

    def forbidden_after_first(url, headers, body, timeout):
        attempted.append(1)
        return TransportResponse(401, b"untrusted provider error body")

    ledger = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        api_key="fixture", model_id="glm-5.3", ledger=ledger,
        enabled=True, route="coding", transport=forbidden_after_first,
    )
    result = ModelG1Runner(
        oracle=FixtureOracle({context: ("multiply", "add")}),
        cohort=cohort,
    ).execute(owner_id="one-source", learned_port=port, fresh_port=port)
    assert len(attempted) == ledger.consumed == 1
    assert port.halted is True
    observations = result.to_dict()["bounded_observations"]
    assert len(observations) == 8
    assert observations[0]["error_class"] == "ProviderTransportRejected"
    assert all(
        item["error_class"] == "ProviderCircuitOpen" for item in observations[1:]
    )
    artifact = {
        "schema": "c3r-live-technical-qualification-v0.1",
        "status": "technical_smoke_not_scientific_evidence",
        "cohort_digest": cohort.digest, "model": "glm-5.3", "route": "coding",
        "report": result.to_dict(), "send_ledger": ledger.to_dict(),
        "scientific_acceptance": False,
    }
    verified = audit_technical_smoke(artifact, expected_cohort_digest=cohort.digest)
    assert verified.status == "structurally_consistent_unattested"
    assert verified.reserved_sends == 1
    assert verified.accepted_actions == 0
    assert verified.to_dict()["scientific_acceptance"] is False


def test_a_missing_seventh_send_cannot_be_explained_by_a_healthy_ledger() -> None:
    artifact, lock = _artifact()
    artifact["send_ledger"]["entries"].pop()
    artifact["send_ledger"]["reserved"] = 7
    verdict = audit_technical_smoke(artifact, expected_cohort_digest=lock)
    assert verdict.status == "rejected_inconsistent_artifact"
    assert "incomplete_without_transport_stop" in verdict.issues



def test_blank_reasoning_only_reply_halts_after_one_http_200_without_losing_tasks() -> None:
    context = "c3r-source-smoke-1"
    cohort = ModelCohortLock(
        tuple(make_task(split="dev", context=context, number=n) for n in range(4)),
        tuple(make_task(split="holdout", context=context, number=n) for n in range(2)),
    )
    sends = []

    def exhausting_transport(url, headers, body, timeout):
        sends.append(url)
        return TransportResponse(
            200,
            json.dumps({
                "choices": [{
                    "message": {"content": "", "reasoning_content": "DO_NOT_LOG"},
                    "finish_reason": "length",
                }],
                "usage": {
                    "completion_tokens": 512,
                    "completion_tokens_details": {"reasoning_tokens": 512},
                },
            }).encode(),
        )

    ledger = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        "fixture", "glm-5.3", ledger, enabled=True,
        route="coding", transport=exhausting_transport,
    )
    outcome = ModelG1Runner(
        oracle=FixtureOracle({context: ("multiply", "add")}),
        cohort=cohort,
    ).execute(owner_id="source", learned_port=port, fresh_port=port)

    assert len(sends) == ledger.consumed == 1
    assert port.halted is True
    assert ledger.records[0].failure_class == "EmptyFinalOutputLengthCap"
    assert ledger.records[0].http_status == 200
    report = outcome.to_dict()
    assert report["development"]["attempts"] == 4
    assert report["qualification_learned"]["attempts"] == 2
    assert report["qualification_fresh"]["attempts"] == 2
    assert report["development"]["empty_output_count"] == 1
    assert report["source_evidence_count"] == 0
    assert report["paired_analyzable"] == 0
    obs = report["bounded_observations"]
    assert obs[0]["status"] == "invalid_format"
    assert obs[0]["finish_reason"] == "length"
    assert obs[0]["completion_tokens_reported"] == 512
    assert all(
        item["error_class"] == "ProviderCircuitOpen" for item in obs[1:]
    )
    assert "DO_NOT_LOG" not in json.dumps(report)

    artifact = {
        "schema": "c3r-live-technical-qualification-v0.1",
        "status": "technical_smoke_not_scientific_evidence",
        "cohort_digest": cohort.digest,
        "model": "glm-5.3",
        "route": "coding",
        "report": report,
        "send_ledger": ledger.to_dict(),
        "scientific_acceptance": False,
    }
    verdict = audit_technical_smoke(artifact, expected_cohort_digest=cohort.digest)
    assert verdict.status == "structurally_consistent_unattested"
    assert verdict.reserved_sends == 1
    assert verdict.accepted_actions == 0

    artifact["report"]["bounded_observations"][0]["output_sha256"] = "1" * 64
    tampered = audit_technical_smoke(artifact, expected_cohort_digest=cohort.digest)
    assert "exhaustion_stop_not_empty_successful_response" in tampered.issues
