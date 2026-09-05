from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path("scripts/preflight_d2_general_api.py")

spec = importlib.util.spec_from_file_location("d2_general_preflight_content_length", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_content_length_200_completes_before_requiring_another_socket(monkeypatch) -> None:
    raw = json.dumps(
        {
            "model": module.MODEL,
            "choices": [{"message": {"content": "OK"}}],
        },
        separators=(",", ":"),
    ).encode()

    class FakeSocket:
        def __init__(self) -> None:
            self.timeouts: list[float] = []

        def settimeout(self, timeout: float) -> None:
            self.timeouts.append(timeout)

    class LengthDelimitedResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = {"Content-Length": str(len(raw))}
            self.length = len(raw)
            self.fp = FakeSocket()
            self.socket = self.fp
            self.remaining = raw

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read1(self, size: int) -> bytes:
            chunk = self.remaining[:size]
            self.remaining = self.remaining[len(chunk) :]
            self.length -= len(chunk)
            if self.length == 0:
                # Mirrors http.client.HTTPResponse: the final length-delimited
                # read closes fp immediately after returning the remaining bytes.
                self.fp = None
            return chunk

    response = LengthDelimitedResponse()

    class LengthDelimitedOpener:
        def open(self, request, timeout):
            return response

    monkeypatch.setattr(module, "OPENER", LengthDelimitedOpener())
    result = module.execute_one("not-a-real-key", module.request_matrix()[0])

    assert response.headers["Content-Length"] == str(len(raw))
    assert response.fp is None
    assert len(response.socket.timeouts) == 1
    assert result["stage"] == "http_success"
    assert result["http_status"] == 200
    assert result["response_body_length"] == len(raw)
    assert result["contract_pass"] is True
    assert "not-a-real-key" not in json.dumps(result)
