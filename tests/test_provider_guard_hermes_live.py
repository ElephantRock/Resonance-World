from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "qualify_provider_guard_hermes_live.py"
SPEC = importlib.util.spec_from_file_location("qualify_provider_guard_hermes_live", SCRIPT_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_request_plan_is_exact_and_provider_execution_is_disabled() -> None:
    plan = mod.load_plan()
    mod.validate_plan(plan)
    assert plan["issue"] == 229
    assert plan["engineering_only"] is True
    assert plan["provider_execution_authorized"] is False
    assert plan["same_request_stream_rerun_allowed"] is False
    assert plan["predecessor_stream_rerun_or_replacement_allowed"] is False
    assert plan["maximum_physical_sends_total"] == 72
    assert plan["logical_probe_count"] == 4
    assert plan["logical_probe_max_concurrency"] == 4


def test_preflight_is_deterministic_and_credential_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv(mod.AUTH_ENV, raising=False)
    first = mod.preflight()
    second = mod.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["execution_marker_absent"] is True
    assert first["provider_send_guard_git_blob_sha"] == mod.GUARD_GIT_BLOB_SHA
    assert first["maximum_physical_sends_total"] == 72


def test_preflight_fails_closed_on_marker_presence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "marker"
    marker.write_text("candidate_sha=" + "0" * 40 + "\n")
    monkeypatch.setattr(mod, "MARKER", marker)
    with pytest.raises(AssertionError, match="marker must be absent"):
        mod.preflight()


def test_plan_drift_is_rejected() -> None:
    plan = json.loads(json.dumps(mod.load_plan()))
    plan["maximum_physical_sends_total"] = 73
    with pytest.raises(AssertionError, match="request-plan drift"):
        mod.validate_plan(plan)


def test_execution_requires_process_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(mod.AUTH_ENV, raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        mod.execute()


def test_bounded_error_persists_only_fingerprint_metadata() -> None:
    result = mod._bounded_error(RuntimeError("HTTP 429 provider_code=1113 secret body text"))
    assert result["error_type"] == "RuntimeError"
    assert result["http_status"] == 429
    assert result["provider_code"] == 1113
    assert result["error_text_length"] > 0
    assert len(result["error_text_sha256"]) == 64
    assert "secret body text" not in json.dumps(result)
