"""Offline-only tests for C3R provider adapter and explicit qualification CLI."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceRequest
from resonance_world.c3r_g1_zai_transport import (
    CODING_ENDPOINT,
    MAX_TOTAL_SENDS,
    STANDARD_ENDPOINT,
    PhysicalSendLedger,
    ProviderBudgetExhausted,
    ProviderTransportRejected,
    TransportResponse,
    ZaiStandardModelPort,
)
from resonance_world.c3r_g2_probe import make_task


def _request(number: int = 0) -> ModelChoiceRequest:
    return ModelChoiceRequest(
        owner_id="source",
        stage="development",
        task=make_task(split="dev", context="opaque-context-1", number=number),
    )


def _response(choice: str = "A") -> TransportResponse:
    return TransportResponse(
        200,
        json.dumps(
            {
                "model": "qualified-model",
                "choices": [{"message": {"content": choice}}],
                "usage": {"prompt_tokens": 17, "completion_tokens": 1},
            }
        ).encode(),
    )


def test_disabled_adapter_cannot_reserve_or_dispatch() -> None:
    seen = []

    def fake_transport(url, headers, body, timeout):
        seen.append(url)
        return _response()

    ledger = PhysicalSendLedger(2)
    port = ZaiStandardModelPort("secret-key", "qualified-model", ledger,
                                transport=fake_transport)
    with pytest.raises(PermissionError, match="disabled"):
        port.complete(_request())
    assert ledger.consumed == 0
    assert seen == []


def test_single_send_pinned_route_and_no_key_in_ledger() -> None:
    seen = []

    def fake_transport(url, headers, body, timeout):
        seen.append((url, headers, json.loads(body), timeout))
        return _response("B")

    ledger = PhysicalSendLedger(2)
    port = ZaiStandardModelPort(
        "secret-key", "qualified-model", ledger, enabled=True, transport=fake_transport
    )
    first = port.complete(_request())
    assert first.output == "B"
    assert first.model_id == "qualified-model"
    assert first.physical_sends_reported == 1
    assert first.prompt_tokens_reported == 17
    assert len(seen) == 1
    url, headers, body, timeout = seen[0]
    assert url == STANDARD_ENDPOINT
    assert headers["Authorization"] == "Bearer secret-key"
    assert body["stream"] is False
    assert body["temperature"] == 0
    assert body["max_tokens"] <= 64
    assert len(body["messages"]) == 1
    assert "expected" not in body["messages"][0]["content"]
    assert timeout <= 30
    assert ledger.consumed == 1
    assert "secret-key" not in json.dumps(ledger.to_dict())
    assert "Bearer" not in json.dumps(ledger.to_dict())


def test_cap_is_reserved_before_dispatch_and_stops_after_one_send() -> None:
    seen = []

    def fake_transport(url, headers, body, timeout):
        seen.append(1)
        return _response()

    ledger = PhysicalSendLedger(1)
    port = ZaiStandardModelPort(
        "secret", "model", ledger, enabled=True, transport=fake_transport
    )
    port.complete(_request(0))
    with pytest.raises(ProviderBudgetExhausted):
        port.complete(_request(1))
    assert len(seen) == ledger.consumed == 1


def test_timeout_consumes_slot_and_is_never_retried() -> None:
    seen = []

    def timeout_transport(url, headers, body, timeout):
        seen.append(1)
        raise TimeoutError("provider secret-like error text")

    ledger = PhysicalSendLedger(1)
    port = ZaiStandardModelPort(
        "secret", "model", ledger, enabled=True, transport=timeout_transport
    )
    with pytest.raises(ProviderTransportRejected, match="transport/shape"):
        port.complete(_request(0))
    assert len(seen) == 1
    assert ledger.consumed == 1
    assert ledger.records[0].failure_class == "TimeoutError"
    assert "secret-like" not in json.dumps(ledger.to_dict())
    with pytest.raises(ProviderBudgetExhausted):
        port.complete(_request(1))
    assert len(seen) == 1


def test_http_error_consumes_budget_and_never_retains_response_body() -> None:
    def bad_transport(url, headers, body, timeout):
        return TransportResponse(429, b"provider raw secret response")

    ledger = PhysicalSendLedger(1)
    port = ZaiStandardModelPort(
        "secret", "model", ledger, enabled=True, transport=bad_transport
    )
    with pytest.raises(ProviderTransportRejected, match="non-200"):
        port.complete(_request())
    assert ledger.records[0].http_status == 429
    assert ledger.records[0].failure_class == "HttpNon200"
    assert "provider raw" not in json.dumps(ledger.to_dict())


@pytest.mark.parametrize("reply", [
    TransportResponse(200, b"not json"),
    TransportResponse(200, b'{"choices": []}'),
    TransportResponse(200, b'{"choices":[{"message":{"content":null}}]}'),
    TransportResponse(200, b"X" * (64 * 1024 + 1)),
    "not a response",
])
def test_invalid_payloads_consume_attempts_without_content_leak(reply) -> None:
    ledger = PhysicalSendLedger(1)
    port = ZaiStandardModelPort(
        "secret", "model", ledger, enabled=True,
        transport=lambda _a, _b, _c, _d: reply,
    )
    with pytest.raises(ProviderTransportRejected):
        port.complete(_request())
    assert ledger.consumed == 1
    assert ledger.records[0].failure_class is not None
    assert ledger.records[0].failure_class != "reserved"


def test_configuration_caps_are_strict() -> None:
    with pytest.raises(ValueError, match="send budget"):
        PhysicalSendLedger(MAX_TOTAL_SENDS + 1)
    with pytest.raises(ValueError, match="send budget"):
        PhysicalSendLedger(0)
    with pytest.raises(ValueError, match="token limit"):
        ZaiStandardModelPort("secret", "model", PhysicalSendLedger(1), max_tokens=100)
    with pytest.raises(ValueError, match="timeout"):
        ZaiStandardModelPort("secret", "model", PhysicalSendLedger(1), timeout_seconds=99)


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "c3r_g1_live_smoke_test", Path(__file__).resolve().parents[1]
        / "scripts" / "run_c3r_g1_live_smoke.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_dry_run_requires_no_secret_or_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("C3R_ZAI_API_KEY", raising=False)
    cli = _load_cli()
    assert cli.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "offline_preflight_no_sends"
    assert report["physical_send_limit"] == 8
    with pytest.raises(SystemExit, match="exactly eight"):
        cli.main(["--max-sends", "500"])


def test_cli_live_fails_closed_without_model_or_key(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _load_cli()
    with pytest.raises(SystemExit, match="explicit model id"):
        cli.main(["--live"])
    monkeypatch.delenv("C3R_ZAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="must be provided privately"):
        cli.main(["--live", "--model", "qualified-model"])


def test_redirects_have_no_follow_up_request() -> None:
    from resonance_world.c3r_g1_zai_transport import _DenyRedirects

    with pytest.raises(ProviderTransportRejected, match="redirects"):
        _DenyRedirects().redirect_request(None, None, 307, None, {}, "https://elsewhere")


def test_default_real_network_transport_is_never_invoked_in_tests() -> None:
    # This test proves only that disabled ports cannot reach the network path.
    with patch(
        "resonance_world.c3r_g1_zai_transport._single_https_post",
        side_effect=AssertionError("network accessed"),
    ) as mock_send:
        ledger = PhysicalSendLedger(1)
        port = ZaiStandardModelPort("secret", "model", ledger, enabled=False)
        with pytest.raises(PermissionError):
            port.complete(_request())
        mock_send.assert_not_called()


def test_manual_workflow_uses_existing_repo_secret_without_new_secret() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "c3r-g1-manual-smoke.yml"
    ).read_text(encoding="utf-8")
    assert "on:\n  workflow_dispatch:" in workflow
    assert "C3R_ZAI_API_KEY: ${{ secrets.ZAI_API_KEY }}" in workflow
    assert "secrets.C3R_ZAI_API_KEY" not in workflow
    assert "c3r-provider-qualification" in workflow
    assert "--live --model" in workflow
    assert "--max-sends 8" in workflow
    assert "\n  push:" not in workflow
    assert "\n  pull_request:" not in workflow



def test_pinned_coding_route_uses_existing_qualified_endpoint() -> None:
    seen = []

    def fake_transport(url, headers, body, timeout):
        seen.append((url, headers, json.loads(body)))
        return _response("A")

    ledger = PhysicalSendLedger(1)
    port = ZaiStandardModelPort(
        "fixture-key", "glm-5.3", ledger, enabled=True,
        route="coding", transport=fake_transport,
    )
    result = port.complete(_request())
    assert result.output == "A"
    assert result.physical_sends_reported == 1
    assert ledger.consumed == 1
    assert len(seen) == 1
    assert seen[0][0] == CODING_ENDPOINT
    assert seen[0][1]["Authorization"] == "Bearer fixture-key"
    assert "Software engineering task" in seen[0][2]["messages"][0]["content"]
    assert "fixture-key" not in json.dumps(ledger.to_dict())


def test_nonpinned_routes_are_rejected_before_any_attempt() -> None:
    with pytest.raises(ValueError, match="provider route"):
        ZaiStandardModelPort(
            "fixture-key", "model", PhysicalSendLedger(1),
            route="https://another.example",  # type: ignore[arg-type]
        )


def test_offline_smoke_declares_selected_coding_route(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    assert cli.main(["--model", "glm-5.3", "--route", "coding"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "offline_preflight_no_sends"
    assert summary["route"] == "coding"
    assert summary["model"] == "glm-5.3"
