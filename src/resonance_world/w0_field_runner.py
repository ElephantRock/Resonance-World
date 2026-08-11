"""Launch pinned Resonance Field with deterministic opaque UUID allocation for W0."""

from __future__ import annotations

import argparse
import hashlib
import runpy
import sys
import uuid
from collections.abc import Callable


def deterministic_uuid4(seed: str) -> Callable[[], uuid.UUID]:
    """Return a repeatable UUIDv4-shaped stream for opaque experiment identities."""

    counter = 0

    def allocate() -> uuid.UUID:
        nonlocal counter
        payload = f"resonance-world:w0:{seed}:{counter}".encode()
        counter += 1
        raw = bytearray(hashlib.sha256(payload).digest()[:16])
        raw[6] = (raw[6] & 0x0F) | 0x40
        raw[8] = (raw[8] & 0x3F) | 0x80
        return uuid.UUID(bytes=bytes(raw))

    return allocate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--uuid-seed", required=True)
    args, field_args = parser.parse_known_args(argv)
    if not field_args:
        raise SystemExit("Field CLI arguments are required")

    # Patch before importing any Resonance Field module. Field remains unchanged;
    # both matched arms receive the identical opaque-identity stream.
    uuid.uuid4 = deterministic_uuid4(args.uuid_seed)  # type: ignore[assignment]
    sys.argv = ["resonance.experiments.cli", *field_args]
    try:
        runpy.run_module("resonance.experiments.cli", run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
