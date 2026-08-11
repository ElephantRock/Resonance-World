"""Materialize the complete preregistered W4-02 coordination learning curve."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .w4_relationship import (
    _evaluate_pairs,
    _load_designs,
    _mean,
    _mission,
    _read_json,
    _train,
)
from .w4a_joint_learning import CommunicationPolicy


def complete_curve(
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    missions_raw = _read_json(missions_path)
    campaign = _read_json(campaign_path)
    formation = [_mission(row) for row in missions_raw["formation"]]
    probes = [_mission(row) for row in missions_raw["formation_probe"]]
    fields = _load_designs(capsules_path, list(campaign["calibration_fields"]))
    communication = CommunicationPolicy(int(campaign["communication_bandwidth_bits"]))
    trials = int(campaign["evaluation_trials_per_mission"])
    checkpoints = [int(item) for item in campaign["learning_checkpoints"]]

    field_rows: list[dict[str, Any]] = []
    for field_id, design in fields.items():
        for checkpoint in checkpoints:
            store = _train(design, formation, checkpoint, communication)
            success = _evaluate_pairs(
                field_id,
                design.original_pairs,
                probes,
                store,
                communication,
                trials,
                salt=f"w4-02-checkpoint-{checkpoint}",
            )
            field_rows.append(
                {
                    "checkpoint": checkpoint,
                    "field_id": field_id,
                    "success": success,
                }
            )

    means = {
        str(checkpoint): _mean(
            [
                float(row["success"])
                for row in field_rows
                if int(row["checkpoint"]) == checkpoint
            ]
        )
        for checkpoint in checkpoints
    }
    result = {
        "checkpoints": means,
        "field_rows": field_rows,
        "learning_gain_0_to_12": means["12"] - means["0"],
        "registered_checkpoints_complete": set(means) == {str(item) for item in checkpoints},
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capsules", type=Path)
    parser.add_argument("missions", type=Path)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    result = complete_curve(args.capsules, args.missions, args.campaign, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
