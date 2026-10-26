"""Qualification Authorization Candidate tests (fully dry, no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resonance_world.experimental_runtime.g1_v9 import (
    MODEL,
    PROPOSED_QUALIFICATION_SEND_CAP,
    PROVIDER,
    DryRunTransport,
    PhysicalSendCapExceeded,
    SendMeter,
    build_qualification_plan,
    default_contract,
    preflight_failure_classes,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_qualification_plan_is_dry_and_unauthorized() -> None:
    plan = build_qualification_plan()
    assert plan.dry_run is True
    assert plan.authorized is False
    assert plan.provider == PROVIDER
    assert plan.model == MODEL
    assert plan.world_count == 1
    assert plan.proposed_send_cap == PROPOSED_QUALIFICATION_SEND_CAP == 8
    assert plan.cap_scope == "connectivity-and-format-probe"
    assert plan.auto_stop_at_cap is True
    assert plan.full_world_model_sends == 420
    assert "authorizes nothing" in plan.notes[0]
    assert any("NOT proposed here" in note for note in plan.notes)


def test_preflight_failure_classes_are_enumerated() -> None:
    classes = preflight_failure_classes()
    assert classes == (
        "auth-failure",
        "malformed-response",
        "send-cap-exceeded",
        "timeout",
    )


def test_send_meter_is_fail_closed_at_the_cap() -> None:
    meter = SendMeter(max_sends=3)
    meter.reserve("send-1", {"n": 1})
    meter.reserve("send-2", {"n": 2})
    meter.reserve("send-3", {"n": 3})
    with pytest.raises(PhysicalSendCapExceeded, match="auto-stop"):
        meter.reserve("send-4", {"n": 4})

    assert meter.used == 3
    assert meter.remaining == 0
    assert meter.refused == 1
    labels = [record.label for record in meter.records()]
    assert labels == ["send-1", "send-2", "send-3"]


def test_send_meter_rejects_invalid_caps() -> None:
    for bad in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            SendMeter(max_sends=bad)  # type: ignore[arg-type]


def test_dry_run_transport_records_without_network_and_respects_the_cap() -> None:
    meter = SendMeter(max_sends=2)
    transport = DryRunTransport(meter=meter)

    first = transport.send("probe-1", {"ping": 1})
    second = transport.send("probe-2", {"ping": 2})
    with pytest.raises(PhysicalSendCapExceeded):
        transport.send("probe-3", {"ping": 3})

    assert first == "dry-run-ack"
    assert second == "dry-run-ack"
    assert meter.used == 2
    assert len(transport.journal) == 2


def test_dry_run_transport_journal_records_exact_payload_digests() -> None:
    from resonance_world.adapters import sha256_json

    meter = SendMeter(max_sends=2)
    transport = DryRunTransport(meter=meter)
    transport.send("a", {"x": 1})
    transport.send("b", {"x": 2})

    assert transport.journal == (
        ("a", sha256_json({"x": 1})),
        ("b", sha256_json({"x": 2})),
    )


def test_qualification_plan_binds_the_frozen_contract() -> None:
    contract = default_contract()
    plan = build_qualification_plan(contract)
    assert plan.contract_digest == contract.digest()
    assert plan.schema == "g1-v9-qualification-plan-v1"
    assert plan.full_world_model_sends == 420  # D is computational: excluded


def test_governance_log_annex_pins_final_values() -> None:
    """Annex A pins 20pp and 18 worlds as FINAL, per the freeze review."""

    log_path = REPO_ROOT / "docs" / "g1-v9-governance-log.md"
    text = log_path.read_text(encoding="utf-8")
    assert "Annex A" in text
    assert "20 percentage points" in text
    assert "Minimum analyzable worlds: 18" in text
    assert "requires a new freeze record" in text


REPO_ROOT = Path(__file__).resolve().parents[1]
