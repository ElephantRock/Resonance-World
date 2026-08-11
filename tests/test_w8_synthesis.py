from __future__ import annotations

import json
from pathlib import Path

from resonance_world.w8_synthesis import synthesize


def _payload(
    *,
    reserve: bool = False,
    circulation: bool = False,
    replacement: str = "replacement_not_sustainable",
    coalition: bool = True,
    charter: bool = False,
    long_label: str = "extractive",
) -> dict[str, object]:
    return {
        "w8_01_source_reserve": {"primary_gate": reserve},
        "w8_02_circulation": {"gate": circulation},
        "w8_03_replacement": {"classification": replacement},
        "w8_04_coalitions": {"gate": coalition},
        "w8_05_integrated_charter": {"gate": charter},
        "w8_06_long_horizon": {
            "neutral": {
                "long_run_label": long_label,
                "compute_normalized_world_stock_growth": -0.1,
            }
        },
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_matching_non_sustainable_pattern_is_not_called_non_replication(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    replication = tmp_path / "replication.json"
    output = tmp_path / "synthesis.json"
    _write(discovery, _payload())
    _write(replication, _payload())

    result = synthesize(
        discovery_path=discovery,
        replication_path=replication,
        output_path=output,
    )

    assert result["status"] == "replicated_non_sustainable_regulatory_regime"
    assert all(result["classification_match"].values())
    assert result["replicated_sustainable_circulation"] is False


def test_true_discovery_replication_disagreement_keeps_nonreplication_label(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    replication = tmp_path / "replication.json"
    output = tmp_path / "synthesis.json"
    _write(discovery, _payload(coalition=True))
    _write(replication, _payload(coalition=False))

    result = synthesize(
        discovery_path=discovery,
        replication_path=replication,
        output_path=output,
    )

    assert result["status"] == "w8_discovery_not_replicated"
    assert result["classification_match"]["w8_04_coalition_surplus"] is False
