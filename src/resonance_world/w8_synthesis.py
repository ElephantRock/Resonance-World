"""Outcome-neutral synthesis correction for W8.

The preregistered base synthesis correctly computes all scientific gates but its
fallback label is contradictory: the intended replicated null/negative label can only
be reached when every success gate is true. This module changes labels only. It never
changes an experiment metric, threshold or gate value.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("W8 phase result must be a JSON object")
    return value


def _write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _replacement_classification(value: Mapping[str, Any]) -> str:
    return str(value.get("classification", value.get("status", "unknown")))


def _outcome_classes(phase: Mapping[str, Any]) -> dict[str, object]:
    return {
        "w8_01_source_reserve": bool(phase["w8_01_source_reserve"]["primary_gate"]),
        "w8_02_circulation": bool(phase["w8_02_circulation"]["gate"]),
        "w8_03_replacement": _replacement_classification(phase["w8_03_replacement"]),
        "w8_04_coalition_surplus": bool(phase["w8_04_coalitions"]["gate"]),
        "w8_05_integrated_charter": bool(phase["w8_05_integrated_charter"]["gate"]),
        "w8_06_long_horizon": str(phase["w8_06_long_horizon"]["neutral"]["long_run_label"]),
    }


def synthesize(
    *,
    discovery_path: str | Path,
    replication_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    discovery = _read_json(discovery_path)
    replication = _read_json(replication_path)

    discovery_classes = _outcome_classes(discovery)
    replication_classes = _outcome_classes(replication)
    classification_match = {
        key: discovery_classes[key] == replication_classes[key]
        for key in discovery_classes
    }

    gates = {
        "w8_01_source_reserve": bool(discovery_classes["w8_01_source_reserve"])
        and bool(replication_classes["w8_01_source_reserve"]),
        "w8_02_circulation": bool(discovery_classes["w8_02_circulation"])
        and bool(replication_classes["w8_02_circulation"]),
        "w8_03_replacement_classification_match": classification_match[
            "w8_03_replacement"
        ],
        "w8_04_coalition_surplus": bool(discovery_classes["w8_04_coalition_surplus"])
        and bool(replication_classes["w8_04_coalition_surplus"]),
        "w8_05_integrated_charter": bool(discovery_classes["w8_05_integrated_charter"])
        and bool(replication_classes["w8_05_integrated_charter"]),
        "w8_06_long_horizon_classification_match": classification_match[
            "w8_06_long_horizon"
        ],
    }

    discovery_long = discovery["w8_06_long_horizon"]["neutral"]
    replication_long = replication["w8_06_long_horizon"]["neutral"]
    sustainable = (
        all(
            gates[key]
            for key in (
                "w8_01_source_reserve",
                "w8_02_circulation",
                "w8_04_coalition_surplus",
                "w8_05_integrated_charter",
                "w8_06_long_horizon_classification_match",
            )
        )
        and str(replication_long["long_run_label"])
        in {"conservative_circulation", "generative_circulation"}
    )
    generative = (
        sustainable
        and str(discovery_long["long_run_label"]) == "generative_circulation"
        and str(replication_long["long_run_label"]) == "generative_circulation"
    )

    if generative:
        status = "replicated_generative_circulation"
    elif sustainable:
        status = "replicated_sustainable_circulation"
    elif all(classification_match.values()):
        status = "replicated_non_sustainable_regulatory_regime"
    else:
        status = "w8_discovery_not_replicated"

    result = {
        "status": status,
        "gates": gates,
        "classification_match": classification_match,
        "discovery_outcome_classes": discovery_classes,
        "replication_outcome_classes": replication_classes,
        "replicated_sustainable_circulation": sustainable,
        "replicated_generative_circulation": generative,
        "discovery_replacement_classification": _replacement_classification(
            discovery["w8_03_replacement"]
        ),
        "replication_replacement_classification": _replacement_classification(
            replication["w8_03_replacement"]
        ),
        "discovery_long_run_label": str(discovery_long["long_run_label"]),
        "replication_long_run_label": str(replication_long["long_run_label"]),
        "discovery_stock_growth": float(
            discovery_long["compute_normalized_world_stock_growth"]
        ),
        "replication_stock_growth": float(
            replication_long["compute_normalized_world_stock_growth"]
        ),
    }
    _write_json(output_path, result)
    return result
