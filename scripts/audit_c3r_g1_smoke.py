"""Safely reconcile a previously downloaded C3R G1 smoke JSON artifact.

This script NEVER contacts a provider, reads an API credential, or executes a
model. A structurally consistent artifact is still unverified and untrusted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resonance_world.c3r_g1_run_audit import audit_technical_smoke

from run_c3r_g1_live_smoke import make_smoke_cohort

MAX_ARTIFACT_BYTES = 512 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline audit of C3R live smoke")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--route", choices=("coding", "standard"), default="coding")
    args = parser.parse_args(argv)

    if not args.artifact.is_file():
        parser.error("smoke artifact does not exist")
    if args.artifact.stat().st_size > MAX_ARTIFACT_BYTES:
        parser.error("smoke artifact exceeds offline audit size cap")
    try:
        source = json.loads(args.artifact.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        source = None
    verdict = audit_technical_smoke(
        source,
        expected_cohort_digest=make_smoke_cohort().digest,
        expected_route=args.route,
        expected_model=args.model,
    )
    print(json.dumps(verdict.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if verdict.status == "structurally_consistent_unattested" else 2


if __name__ == "__main__":
    raise SystemExit(main())
