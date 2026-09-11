from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_d2_terminal_adapter_v2.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("qualify_d2_terminal_adapter_v2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v2_probe_stream_is_fresh_and_balanced() -> None:
    module = _load_module()
    probes = module.generate_probes()
    assert len(probes) == 72
    assert [row["logical_index"] for row in probes] == list(range(72))
    budgets = Counter(row["development_budget"] for row in probes)
    assert budgets == Counter({40: 24, 80: 24, 160: 24})
    assert {row["seed"] for row in probes}.isdisjoint(set(range(1_000_000, 1_000_072)))
    assert min(row["seed"] for row in probes) == 2_000_000
    assert max(row["seed"] for row in probes) == 2_000_071
    assert all(row["probe_id"].startswith("adapter_v2_") for row in probes)
    assert len({row["probe_id"] for row in probes}) == 72


def test_v2_frozen_contract_and_preserved_regression() -> None:
    module = _load_module()
    probes = module.validate_frozen_files()
    assert len(probes) == 72
    result = module.preflight()
    assert result["schema"] == "d2-terminal-adapter-v2-preflight-v0.1"
    assert result["issue"] == 251
    assert result["provider_execution_performed"] is False
    assert result["execution_marker_absent"] is True
    assert result["fresh_seed_namespace"] == "rw.d2-terminal-adapter.v2"
    assert result["fresh_seed_start"] == 2_000_000
    assert result["preserved_evidence_regression"] == {
        "effective_completed": 72,
        "native_completed": 64,
        "terminal_overrides": 8,
    }


def test_v2_core_patch_keeps_predecessor_stream_distinct() -> None:
    module = _load_module()
    module._patch_core()
    assert module.core.ISSUE == 251
    assert module.core.AUTH_ENV == "D2_TERMINAL_ADAPTER_V2_AUTHORIZED"
    assert module.core.MARKER.name == "RUN_D2_TERMINAL_ADAPTER_V2_QUALIFICATION"
    assert module.core.validate_frozen_files is module.validate_frozen_files
    assert module.core.load_probes is module.generate_probes
