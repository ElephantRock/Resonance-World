"""Run the C3R G1 sealed evaluator in a separate, local Python process.

For test/engineering use only. The caller MUST NOT share a Python process
with the grader. A separate process owned by the SAME OS user does not form
a hardened security boundary or independently attest evaluator authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

from .c3r_g1_multischema import V2Design
from .c3r_g1_sealed_evaluator import SealedEvaluator

MAX_LINE_BYTES = 4096
MAX_MESSAGES = 482  # 480 submit calls, one finalize, plus margin


def _load_private_key(path: Path) -> bytes:
    """Reject symlinks, non-regular files, group/other-readable keys."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("private evaluator key file permissions are unsafe")
        if info.st_size > 65:
            raise ValueError("private evaluator key file is oversized")
        content = os.read(fd, 66).strip()
    finally:
        os.close(fd)
    if not re.fullmatch(rb"[0-9a-fA-F]{64}", content):
        raise ValueError("private evaluator key must be 32 bytes in hex")
    return bytes.fromhex(content.decode("ascii"))


def _emit(record: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(
        record, sort_keys=True, separators=(",", ":")
    ) + "\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sealed local G1 evaluator worker")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--units", type=int, default=8)
    parser.add_argument("--development", type=int, default=6)
    parser.add_argument("--qualification", type=int, default=8)
    parser.add_argument("--public-seed", type=int, default=20261022)
    parser.add_argument("--model-id", default="offline-schema-fixture")
    args = parser.parse_args(argv)

    try:
        design = V2Design(
            units=args.units,
            development_per_family=args.development,
            qualification_per_family=args.qualification,
            public_seed=args.public_seed,
            model_id=args.model_id,
        )
        key = _load_private_key(args.key_file)
        grader = SealedEvaluator(design.freeze(), private_key=key)
    except (OSError, ValueError, TypeError):
        _emit({
            "schema": "c3r-g1-evaluator-error-v0.1",
            "status": "rejected_before_ready",
        })
        return 2

    _emit(grader.ready().payload)
    for _ in range(MAX_MESSAGES):
        line = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
        if not line:
            # EOF before finalize is always unsuccessful.
            return 2
        if len(line) > MAX_LINE_BYTES:
            _emit({"schema": "c3r-g1-evaluator-error-v0.1",
                   "status": "invalid_or_oversized_message"})
            return 2
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("message must be a JSON object")
            if message.get("op") == "submit":
                reply = grader.submit(message)
            elif message.get("op") == "finalize":
                reply = grader.finalize(message)
            else:
                raise ValueError("unsupported message type")
        except (ValueError, TypeError, KeyError):
            _emit({
                "schema": "c3r-g1-evaluator-error-v0.1",
                "status": "invalid_request",
            })
            return 2
        _emit(reply.payload)
        if message["op"] == "finalize":
            return 0
    _emit({"schema": "c3r-g1-evaluator-error-v0.1",
           "status": "message_limit_exceeded"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
