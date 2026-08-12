"""Execute preregistered CG-1 against the pinned W3 discovery-source artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resonance_world.context_graph_w3 import run_cg1


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="experiments/context_graph/cg1-w3.json")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output", default="output/context_graph/cg1-w3-result.json")
    args = parser.parse_args()

    config = _read_json(args.config)
    source = Path(args.source_dir)
    paths = {
        "runs.csv": source / "runs.csv",
        "outcomes.csv": source / "outcomes.csv",
        "tasks.csv": source / "tasks.csv",
        "bids.csv": source / "bids.csv",
    }
    result = run_cg1(paths, config)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit("CG-1 failed preregistered held-out gates")


if __name__ == "__main__":
    main()
