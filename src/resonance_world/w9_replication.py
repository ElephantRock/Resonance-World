"""W9-07 unseen-replication synthesis over frozen W9 stage outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

RESULT_VERSION = "w9-07-replication-synthesis-v0.1"
EXPECTED_SEEDS = [4211, 4331, 4451, 4571, 4691]

# These are discovery outcomes accepted before the unseen replication cohort was
# generated. They are prerequisites for the nested "replicated_*" claims and are
# intentionally not recomputed from replication data.
DISCOVERY_FROZEN = {
    "W9-00B": {
        "classification": "calibrated_source_cost_estimator",
        "gate": True,
    },
    "W9-01": {
        "classification": "criticality_allocation_ineffective",
        "gate": False,
    },
    "W9-02": {
        "classification": "leasing_switching_fragile",
        "gate": False,
    },
    "W9-03": {
        "classification": "redundancy_not_efficient",
        "gate": False,
    },
    "W9-04": {
        "K": ["none"],
        "gate": False,
    },
    "W9-05": {
        "classification": "integrated_static_gate_failed",
        "gate": False,
        "selected_mechanisms": [],
    },
    "W9-06": {
        "classification": "long_horizon_gate_failed",
        "gate": False,
    },
}


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_replication_phase(stage: str, value: Mapping[str, Any]) -> None:
    if value.get("phase") != "replication":
        raise ValueError(f"{stage} is not a replication result")
    if "seeds" in value:
        seeds = [int(seed) for seed in value["seeds"]]
        if seeds != EXPECTED_SEEDS:
            raise ValueError(f"{stage} replication seed mismatch: {seeds}")


def _selected_w9_05_is_frozen(value: Mapping[str, Any]) -> bool:
    return (
        value.get("selected_mechanisms") == []
        and value.get("upstream_eligibility")
        == {"C": False, "L": False, "P": False, "K": []}
        and value.get("structural_status") == "no_upstream_eligible_w9_mechanisms"
    )


def synthesize_replication(
    *,
    calibration: Mapping[str, Any],
    allocation: Mapping[str, Any],
    leasing: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    coalition: Mapping[str, Any],
    integrated: Mapping[str, Any],
    long_horizon: Mapping[str, Any],
) -> dict[str, Any]:
    stages = {
        "W9-00B": calibration,
        "W9-01": allocation,
        "W9-02": leasing,
        "W9-03": portfolio,
        "W9-04": coalition,
        "W9-05": integrated,
        "W9-06": long_horizon,
    }
    for name, value in stages.items():
        _require_replication_phase(name, value)

    if not _selected_w9_05_is_frozen(integrated):
        raise ValueError("W9-05 replication changed the discovery-frozen regime")
    if long_horizon.get("selected_mechanisms") != []:
        raise ValueError("W9-06 replication changed the discovery-frozen regime")
    if long_horizon.get("version") != "w9-06-long-horizon-result-v0.6":
        raise ValueError("W9-06 replication must use the accepted v0.6 accounting law")

    replication_calibrated = (
        calibration.get("calibration", {}).get("label")
        == "calibrated_source_cost_estimator"
    )
    replication_w9_01_gate = bool(allocation.get("gate"))
    replication_w9_02_gate = bool(leasing.get("robust_gate"))
    replication_w9_05_gate = bool(integrated.get("integrated_static_gate"))
    replication_w9_06_gate = bool(long_horizon.get("long_horizon_gate"))

    nested = {
        "replicated_calibrated_criticality_pricing": (
            DISCOVERY_FROZEN["W9-00B"]["gate"] and replication_calibrated
        ),
        "replicated_tradeoff_reduction": (
            DISCOVERY_FROZEN["W9-01"]["gate"] and replication_w9_01_gate
        ),
        "replicated_sustainable_capability_leasing": (
            DISCOVERY_FROZEN["W9-02"]["gate"] and replication_w9_02_gate
        ),
        "replicated_regenerative_allocation": (
            DISCOVERY_FROZEN["W9-00B"]["gate"]
            and replication_calibrated
            and DISCOVERY_FROZEN["W9-05"]["gate"]
            and replication_w9_05_gate
            and DISCOVERY_FROZEN["W9-06"]["gate"]
            and replication_w9_06_gate
        ),
    }

    stage_results = {
        "W9-00B": {
            "classification": calibration.get("calibration", {}).get("label"),
            "mae_pp": calibration.get("calibration", {}).get("mae_pp"),
            "signed_bias_pp": calibration.get("calibration", {}).get("signed_bias_pp"),
            "spearman_rho": calibration.get("calibration", {}).get("spearman_rho"),
            "high_cost_safe_rate": calibration.get("calibration", {}).get(
                "high_cost_safe_rate"
            ),
        },
        "W9-01": {
            "classification": allocation.get("classification"),
            "gate": replication_w9_01_gate,
            "gates": allocation.get("gates"),
        },
        "W9-02": {
            "classification": leasing.get("classification"),
            "zero_recovery_gate": bool(leasing.get("zero_recovery_gate")),
            "recovery_gate": bool(leasing.get("recovery_gate")),
            "robust_gate": replication_w9_02_gate,
        },
        "W9-03": {
            "classification": portfolio.get("classification"),
            "eligible_for_w9_05_P": bool(portfolio.get("eligible_for_w9_05_P")),
        },
        "W9-04": {
            "K_replication_diagnostic": coalition.get("K"),
            "discovery_frozen_K": ["none"],
        },
        "W9-05": {
            "classification": integrated.get("classification"),
            "integrated_static_gate": replication_w9_05_gate,
            "gates": integrated.get("gates"),
            "selected_mechanisms": integrated.get("selected_mechanisms"),
        },
        "W9-06": {
            "classification": long_horizon.get("classification"),
            "long_horizon_gate": replication_w9_06_gate,
            "gates": long_horizon.get("gates"),
            "selected_mechanisms": long_horizon.get("selected_mechanisms"),
        },
    }

    # This payload contains only decision-relevant scientific synthesis. Full
    # stage hashes are intentionally kept outside it as provenance fingerprints.
    scientific_payload: dict[str, Any] = {
        "version": RESULT_VERSION,
        "phase": "replication",
        "status": "replication_complete",
        "seeds": list(EXPECTED_SEEDS),
        "discovery_frozen_prerequisites": DISCOVERY_FROZEN,
        "replication_stage_results": stage_results,
        "nested_outcomes": nested,
        "discovery_frozen_regime_preserved": True,
        "selected_mechanisms": [],
    }
    result: dict[str, Any] = {
        **scientific_payload,
        "stage_payload_sha256": {
            name: _canonical_sha256(value) for name, value in stages.items()
        },
        "scientific_payload_sha256": _canonical_sha256(scientific_payload),
    }
    if "practice_by_skill" in json.dumps(result, sort_keys=True):
        raise AssertionError("private practice leaked into W9-07 synthesis")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--allocation", required=True, type=Path)
    parser.add_argument("--leasing", required=True, type=Path)
    parser.add_argument("--portfolio", required=True, type=Path)
    parser.add_argument("--coalition", required=True, type=Path)
    parser.add_argument("--integrated", required=True, type=Path)
    parser.add_argument("--long-horizon", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    result = synthesize_replication(
        calibration=_read_json(args.calibration),
        allocation=_read_json(args.allocation),
        leasing=_read_json(args.leasing),
        portfolio=_read_json(args.portfolio),
        coalition=_read_json(args.coalition),
        integrated=_read_json(args.integrated),
        long_horizon=_read_json(args.long_horizon),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
