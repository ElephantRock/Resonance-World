"""Live pilot launcher: one process runs the full single-universe world.

Requires ZAI_API_KEY in the environment. Progress prints to stdout
(line-buffered); the durable evidence is the custody ledger plus the
kernel stores, and the final report lands in custody/pilot-report.json.
"""

import os
import sys

from resonance_world.experimental_runtime.g1_v9.pilot import run_pilot

CUSTODY_DIR = r"D:\Documents\deepseek-harness\qualification-custody"


def main() -> int:
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("ZAI_API_KEY missing from the environment", file=sys.stderr)
        return 2
    report = run_pilot(
        custody_dir=CUSTODY_DIR,
        credential_provider=lambda: api_key,
        pacing_seconds=1.5,
    )
    print(report.to_json())
    return 0 if report.world_valid_for_analysis else 1


if __name__ == "__main__":
    raise SystemExit(main())
