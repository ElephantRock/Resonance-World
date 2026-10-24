"""Offline-only tests for C3R provider adapter and explicit qualification CLI."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceRequest
from resonance_world.c3r_g1_zai_transport import (
    CODING_ENDPOINT,
    DEFAULT_GENERATION_TOKENS,
    MAX_GENERATION_TOKENS,
    MAX_RESPONSE_BYTES,
    MAX_TOTAL_SENDS,
    STANDARD_ENDPOINT,
    PhysicalSendLedger,
    ProviderBudgetExhausted,
    ProviderCircuitOpen,
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
    assert body["max_tokens"] == DEFAULT_GENERATION_TOKENS
    assert len(body["messages"]) == 1
    assert "expected" not in body["messages"][0]["content"]
    assert timeout == 180
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
    assert port.halted is True
    assert "secret-like" not in json.dumps(ledger.to_dict())
    with pytest.raises(ProviderCircuitOpen):
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
    TransportResponse(200, b"X" * (MAX_RESPONSE_BYTES + 1)),
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
        ZaiStandardModelPort(
            "secret", "model", PhysicalSendLedger(1),
            max_tokens=MAX_GENERATION_TOKENS + 1,
        )
    with pytest.raises(ValueError, match="timeout"):
        ZaiStandardModelPort("secret", "model", PhysicalSendLedger(1), timeout_seconds=301)


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
    assert seen[0][2]["thinking"] == {"type": "enabled"}
    assert seen[0][2]["reasoning_effort"] == "low"
    assert seen[0][2]["max_tokens"] == DEFAULT_GENERATION_TOKENS
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



def test_provider_rejection_closes_circuit_before_any_second_send() -> None:
    attempted = []

    def forbidden_transport(url, headers, body, timeout):
        attempted.append(1)
        return TransportResponse(429, b"untrusted quota message")

    ledger = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        "fixture", "glm-5.3", ledger, enabled=True,
        route="coding", transport=forbidden_transport,
    )
    with pytest.raises(ProviderTransportRejected, match="non-200"):
        port.complete(_request(0))
    for index in range(1, 8):
        with pytest.raises(ProviderCircuitOpen, match="circuit"):
            port.complete(_request(index))
    assert len(attempted) == 1
    assert ledger.consumed == 1
    assert port.halted is True



def test_forced_reasoning_metadata_is_bounded_and_not_retained_raw() -> None:
    response = TransportResponse(
        200,
        json.dumps({
            "choices": [{
                "message": {"content": "A", "reasoning_content": "PRIVATE_REASONING_DATA"},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 87,
                "completion_tokens_details": {"reasoning_tokens": 84},
            },
        }).encode(),
    )
    port = ZaiStandardModelPort(
        "fixture", "glm-5.3", PhysicalSendLedger(1), enabled=True, route="coding",
        transport=lambda *_args: response,
    )
    completion = port.complete(_request())
    assert completion.finish_reason == "stop"
    assert completion.reasoning_present is True
    assert completion.reasoning_tokens_reported == 84
    assert "PRIVATE_REASONING_DATA" not in repr(completion)
    assert "PRIVATE_REASONING_DATA" not in json.dumps(port.ledger.to_dict())


def test_forced_reasoning_diagnostics_detect_blank_at_token_cap() -> None:
    response = TransportResponse(
        200,
        json.dumps({
            "choices": [{
                "message": {"content": "", "reasoning_content": "PRIVATE_REASONING_DATA"},
                "finish_reason": "length",
            }],
            "usage": {
                "prompt_tokens": 117,
                "completion_tokens": 512,
                "completion_tokens_details": {"reasoning_tokens": 512},
            },
        }).encode(),
    )
    port = ZaiStandardModelPort(
        "fixture", "glm-5.3", PhysicalSendLedger(1), enabled=True, route="coding",
        transport=lambda *_args: response,
    )
    completion = port.complete(_request())
    assert completion.output == ""
    assert completion.finish_reason == "length"
    assert completion.reasoning_present is True
    assert completion.reasoning_tokens_reported == 512
    assert completion.physical_sends_reported == 1
    assert port.halted is True
    assert port.ledger.consumed == 1
    assert port.ledger.records[0].http_status == 200
    assert port.ledger.records[0].failure_class == "EmptyFinalOutputLengthCap"
    with pytest.raises(ProviderCircuitOpen):
        port.complete(_request(1))



def test_unknown_provider_finish_reason_is_normalized_not_leaked() -> None:
    raw_metadata = "UNTRUSTED_FINISH_TEXT_DO_NOT_STORE"
    response = TransportResponse(
        200,
        json.dumps({
            "choices": [
                {"message": {"content": "B"}, "finish_reason": raw_metadata},
            ],
            "usage": {"completion_tokens": 3},
        }).encode(),
    )
    port = ZaiStandardModelPort(
        "fixture", "glm-5.3", PhysicalSendLedger(1), enabled=True,
        route="coding", transport=lambda *_args: response,
    )
    completion = port.complete(_request())
    assert completion.finish_reason == "other"
    assert completion.output == "B"
    assert raw_metadata not in repr(completion)
    assert raw_metadata not in json.dumps(port.ledger.to_dict())



def test_glm52_legacy_model_always_requests_thinking_enabled() -> None:
    sent = []

    def capture(url, headers, body, timeout):
        sent.append(json.loads(body))
        return TransportResponse(
            200, json.dumps({
                "choices": [{"finish_reason": "stop", "message": {"content": "A"}}],
                "usage": {"prompt_tokens": 25, "completion_tokens": 1},
            }).encode(),
        )

    port = ZaiStandardModelPort(
        api_key="credential-only-for-test", model_id="glm-5.2",
        ledger=PhysicalSendLedger(1), transport=capture,
        thinking_mode="default", route="coding", enabled=True,
        max_tokens=256,
    )
    answer = port.complete_prompt("Choose exactly A or B")
    assert answer.output == "A"
    assert sent[0]["thinking"] == {"type": "enabled"}
    assert "reasoning_effort" not in sent[0]
    assert sent[0]["model"] == "glm-5.2"
    assert sent[0]["max_tokens"] == 256


def test_glm53_cannot_disable_thinking_even_when_provider_enabled() -> None:
    for model in ("glm-5.3", "glm-5.3-flash", "unverified-model"):
        with pytest.raises(ValueError, match="disable"):
            ZaiStandardModelPort(
                api_key="test", model_id=model, ledger=PhysicalSendLedger(1),
                enabled=True, thinking_mode="disabled",
            )



def test_glm47_legacy_model_no_longer_attempts_disabling() -> None:
    observed = []

    def capture(_url, _headers, body, _timeout):
        observed.append(json.loads(body))
        return TransportResponse(
            200, json.dumps({
                "choices": [{"finish_reason": "stop", "message": {"content": "B"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 1},
            }).encode(),
        )

    result = ZaiStandardModelPort(
        api_key="fixture-secret", model_id="glm-4.7",
        ledger=PhysicalSendLedger(1), enabled=True,
        route="coding", thinking_mode="default", max_tokens=512,
        transport=capture,
    ).complete_prompt("Reply with A or B.")
    assert result.output == "B"
    assert observed[0]["model"] == "glm-4.7"
    assert observed[0]["thinking"] == {"type": "enabled"}
    assert observed[0]["max_tokens"] == 512
    assert "reasoning_effort" not in observed[0]



@pytest.mark.parametrize("effort", ["low", "high", "max"])
def test_glm53_reasoning_levels_explicit_and_thinking_enabled(effort: str) -> None:
    sent = []

    def capture(_url, _headers, body, _timeout):
        sent.append(json.loads(body))
        return TransportResponse(
            200, json.dumps({
                "choices": [{"finish_reason": "stop",
                             "message": {"content": "A"}}],
                "usage": {"prompt_tokens": 18, "completion_tokens": 2},
            }).encode(),
        )

    port = ZaiStandardModelPort(
        api_key="fixture", model_id="glm-5.3",
        ledger=PhysicalSendLedger(1), enabled=True, route="coding",
        reasoning_effort=effort, transport=capture,
    )
    assert port.complete_prompt("Reply A or B.").output == "A"
    assert sent[0]["thinking"] == {"type": "enabled"}
    assert sent[0]["reasoning_effort"] == effort


def test_glm53_rejects_none_or_disabled_effort_without_sending() -> None:
    for invalid in ("none", "disabled", "medium", ""):
        with pytest.raises(ValueError, match="reasoning effort"):
            ZaiStandardModelPort(
                api_key="fixture", model_id="glm-5.3",
                ledger=PhysicalSendLedger(1), enabled=True,
                reasoning_effort=invalid,
            )
