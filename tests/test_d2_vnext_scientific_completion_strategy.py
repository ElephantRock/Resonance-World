from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import qualify_d2_vnext_scientific_completion as q  # noqa: E402


def test_trajectory_preserves_prior_strategy_when_response_omits_strategy(monkeypatch: Any) -> None:
    specs = [
        {"phase": "a", "shape": "developed_development", "seed": 1, "arm": "developed_40"},
        {"phase": "b", "shape": "developed_development", "seed": 2, "arm": "developed_40"},
        {"phase": "c", "shape": "developed_evaluation", "seed": 3, "arm": "developed_40"},
    ]
    seen: list[str] = []
    returned = iter(["learned-strategy", "", "replacement"])

    monkeypatch.setattr(q, "trajectory_specs", lambda _index: specs)

    def fake_run_call(
        _budget: q.Budget,
        _logical: int,
        _call_id: str,
        _profile: dict[str, Any],
        _shape: str,
        _seed: int,
        strategy: str,
    ) -> tuple[dict[str, Any], str]:
        seen.append(strategy)
        return {"status": "success"}, next(returned)

    monkeypatch.setattr(q, "run_call", fake_run_call)
    q.run_trajectory(q.Budget(), 0, q.PROFILES[0])

    assert seen == ["", "learned-strategy", "learned-strategy"]
