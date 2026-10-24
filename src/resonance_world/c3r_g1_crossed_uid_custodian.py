"""One-request grade-free custody socket worker for offline crossed G1.

Runs only as the custodian UID; writes one local O_EXCL deposit. Does not
produce independent custody, external timestamp or scientific acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from resonance_world.c3r_g1_crossed_source_deposit import (
    deposit_source_receipts,
    read_private_seed,
)

MAX_SOURCE_MESSAGE_BYTES = 256 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crossed G1 offline custody worker")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--custodian-private-seed-file", type=Path, required=True)
    parser.add_argument("--evaluator-public-key-file", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        line = sys.stdin.buffer.readline(MAX_SOURCE_MESSAGE_BYTES + 1)
        if not line or len(line) > MAX_SOURCE_MESSAGE_BYTES:
            raise ValueError("source transcript absent or oversized")
        request = json.loads(line)
        if (not isinstance(request, dict)
                or set(request) != {"op", "source_receipts"}
                or request["op"] != "deposit"
                or not isinstance(request["source_receipts"], list)):
            raise ValueError("invalid custody request")
        expected_public = args.evaluator_public_key_file.read_text(
            encoding="ascii"
        ).strip()
        signed, _location = deposit_source_receipts(
            source_receipts=tuple(request["source_receipts"]),
            expected_run_id=args.run_id,
            evaluator_public_key_hex=expected_public,
            custodian_private_seed=read_private_seed(
                args.custodian_private_seed_file
            ),
            destination=args.destination,
        )
        answer = {
            "phase": "source_custody_claim_signed_locally",
            "signed_custody_receipt": signed,
            "external_custody_attested": False,
            "scientific_acceptance": False,
        }
        sys.stdout.write(json.dumps(answer, sort_keys=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return 0
    except (ValueError, OSError, TypeError, KeyError, UnicodeError):
        sys.stdout.write(json.dumps({
            "phase": "offline_custody_rejected", "scientific_acceptance": False,
        }, sort_keys=True) + "\n")
        sys.stdout.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
