"""GLM deep-reasoning output-budget regression tests, always zero real sends."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_calibration_audit import (
    _request_digest,
    audit_calibration_transport,
)
from resonance_world.c3r_g1_host_campaign_budget import HostCampaignBudget
from resonance_world.c3r_g1_multischema_calibration import (
    CalibrationRunner,
    make_calibration_plan,
)
from resonance_world.c3r_g1_zai_transport import (
    CODING_ENDPOINT,
    DEFAULT_GENERATION_TOKENS,
    MAX_GENERATION_TOKENS,
    PhysicalSendLedger,
    TransportResponse,
    ZaiStandardModelPort,
)


@pytest.mark.parametrize("output_budget", [16384, 32768, 65536, 131072])
def test_configured_reasoning_budget_is_preserved_through_end_to_end_audit(
    output_budget: int,
) -> None:
    outbound: list[dict[str, object]] = []

    def fake_transport(_url, _headers, raw_body, timeout):
        body = json.loads(raw_body)
        assert timeout == 180
        outbound.append(body)
        return TransportResponse(
            200,
            json.dumps({
                "choices": [
                    {"message": {"content": "A", "reasoning_content": "synthetic"},
                     "finish_reason": "stop"},
                ],
                "usage": {
                    "completion_tokens": output_budget // 2,
                    "completion_tokens_details": {
                        "reasoning_tokens": output_budget // 2 - 1
                    },
                },
            }).encode(),
        )

    ledger = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        api_key="synthetic-no-network", model_id="glm-5.3",
        ledger=ledger, enabled=True, route="coding",
        max_tokens=output_budget, transport=fake_transport,
    )
    report = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert len(outbound) == ledger.consumed == 8
    assert all(item["max_tokens"] == output_budget for item in outbound)
    assert all(item["reasoning_effort"] == "low" for item in outbound)
    assert report["technical_yield_gate"]["passed"] is True
    verdict = audit_calibration_transport(
        report, ledger.to_dict(), expected_model="glm-5.3",
        expected_route="coding", max_tokens=output_budget,
    )
    assert verdict.verdict == "structurally_consistent_unattested"
    assert verdict.to_dict()["physical_sends_authenticated"] is False
    assert verdict.to_dict()["scientific_acceptance"] is False
    assert audit_calibration_transport(
        report, ledger.to_dict(), max_tokens=512,
        expected_route="coding",
    ).verdict == "rejected"


def test_host_budget_and_transport_agree_on_32768_token_body(tmp_path: Path) -> None:
    tokens = 32768
    plan = make_calibration_plan()
    digests = tuple(
        _request_digest(x.prompt(), model="glm-5.3", max_tokens=tokens)
        for x in plan
    )
    guard = HostCampaignBudget(
        tmp_path / "budget.json", campaign_id="g1-deep-thinking-fixture-2026",
        endpoint=CODING_ENDPOINT, planned_digests=digests, maximum=8,
    )
    guard.initialize()
    sends: list[dict] = []

    def fake_transport(_url, _headers, body, _timeout):
        sends.append(json.loads(body))
        return TransportResponse(
            200, b'{"choices":[{"message":{"content":"B"},"finish_reason":"stop"}]}'
        )

    port = ZaiStandardModelPort(
        api_key="synthetic-no-network", model_id="glm-5.3",
        ledger=PhysicalSendLedger(8), enabled=True, route="coding",
        max_tokens=tokens, campaign_budget=guard,
        transport=fake_transport,
    )
    report = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert report["answered_calls"] == 8
    assert len(sends) == guard.inspect()["reserved"] == 8
    assert all(item["max_tokens"] == tokens for item in sends)
    assert report["scientific_acceptance"] is False


def test_budget_default_and_hard_ceiling_are_distinct_from_context_size() -> None:
    assert DEFAULT_GENERATION_TOKENS == 16384
    assert MAX_GENERATION_TOKENS == 131072
    with pytest.raises(ValueError, match="generation token limit"):
        ZaiStandardModelPort(
            "synthetic", "glm-5.3", PhysicalSendLedger(1),
            max_tokens=MAX_GENERATION_TOKENS + 1,
        )
    with pytest.raises(ValueError, match="generation token limit"):
        ZaiStandardModelPort(
            "synthetic", "glm-5.3", PhysicalSendLedger(1),
            max_tokens=True,
        )


def test_legacy_live_smoke_default_dry_run_exposes_large_budget(
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable, "scripts/run_c3r_g1_live_smoke.py",
            "--model", "glm-5.3", "--route", "coding",
        ],
        cwd=root, capture_output=True, text=True, check=False, timeout=20,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["status"] == "offline_preflight_no_sends"
    assert report["generation_max_tokens"] == 16384
    assert report["per_call_timeout_seconds"] == 180.0
    assert report["scientific_acceptance"] is False
    assert report["requires_live_opt_in"] is True
