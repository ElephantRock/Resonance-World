"""Linux UID-pinned one-client socket boundary for fourth G1 offline fixture.

Same-host disposable UIDs and SO_PEERCRED are testable engineering isolation;
this is not an independent evaluator, custodian or external evidence service.
No model/provider network access, credential plumbing, or live dispatch.
"""

from __future__ import annotations

import argparse
import os
import socket
import stat
import struct
import subprocess
import sys
from pathlib import Path

MAX_UNTRUSTED_CONNECTIONS = 8


def serve_fixture(*, path: Path, peer_uid: int, role: str, arguments: list[str]) -> int:
    """Permit exactly one agent UID before starting the private-key worker."""
    if role not in ("evaluator", "custodian", "witness"):
        raise ValueError("unknown offline service role")
    if not hasattr(socket, "SO_PEERCRED") or type(peer_uid) is not int or peer_uid < 1:
        raise ValueError("Linux SO_PEERCRED and nonroot peer UID required")
    if not path.is_absolute() or len(os.fsencode(path)) >= 104:
        raise ValueError("invalid Linux socket path")
    parent = path.parent
    info = parent.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o022 or os.geteuid() == 0):
        raise ValueError("service socket parent requires nonroot owner and safe permissions")
    if path.exists() or path.is_symlink():
        raise ValueError("refuse to replace existing socket")
    module = {
        "evaluator": "resonance_world.c3r_g1_crossed_local_evaluator",
        "custodian": "resonance_world.c3r_g1_crossed_uid_custodian",
        "witness": "resonance_world.c3r_g1_crossed_uid_witness",
    }[role]
    old_mask = os.umask(0o117)
    try:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(str(path))
        finally:
            os.umask(old_mask)
        try:
            os.chmod(path, 0o660)
            server.listen(1)
            server.settimeout(20)
            for _ in range(MAX_UNTRUSTED_CONNECTIONS):
                client, _ = server.accept()
                try:
                    packed = client.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"),
                    )
                    _pid, uid, _gid = struct.unpack("3i", packed)
                    if uid != peer_uid:
                        continue
                    completed = subprocess.run(
                        [sys.executable, "-m", module, *arguments],
                        stdin=client, stdout=client, stderr=subprocess.DEVNULL,
                        check=False, timeout=90,
                    )
                    return completed.returncode
                finally:
                    client.close()
            return 2
        finally:
            server.close()
    finally:
        if path.exists() and stat.S_ISSOCK(path.lstat().st_mode):
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot offline UID-pinned G1 fixture")
    parser.add_argument("--role", choices=("evaluator", "custodian", "witness"),
                        required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--allowed-peer-uid", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-seed-file", type=Path)
    parser.add_argument("--signing-seed-file", type=Path)
    parser.add_argument("--custodian-public-key-file", type=Path)
    parser.add_argument("--custodian-private-seed-file", type=Path)
    parser.add_argument("--evaluator-public-key-file", type=Path)
    parser.add_argument("--witness-public-key-file", type=Path)
    parser.add_argument("--witness-seed-file", type=Path)
    parser.add_argument("--enrollment-file", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.role == "evaluator":
            if (None in (args.target_seed_file, args.signing_seed_file,
                         args.custodian_public_key_file)
                    or (args.witness_public_key_file is None)
                    != (args.enrollment_file is None)
                    or any(x is not None for x in (
                        args.custodian_private_seed_file, args.evaluator_public_key_file,
                        args.witness_seed_file, args.destination,
                    ))):
                raise ValueError("invalid evaluator fixture key roles")
            worker_args = [
                "--run-id", args.run_id,
                "--target-seed-file", str(args.target_seed_file),
                "--signing-seed-file", str(args.signing_seed_file),
                "--custodian-public-key-file", str(args.custodian_public_key_file),
            ]
            if args.enrollment_file is not None:
                worker_args.extend([
                    "--enrollment-file", str(args.enrollment_file),
                    "--witness-public-key-file", str(args.witness_public_key_file),
                ])
        elif args.role == "custodian":
            if (None in (args.custodian_private_seed_file,
                         args.evaluator_public_key_file, args.destination)
                    or any(x is not None for x in (
                        args.target_seed_file, args.signing_seed_file,
                        args.custodian_public_key_file, args.witness_public_key_file,
                        args.witness_seed_file, args.enrollment_file,
                    ))):
                raise ValueError("invalid custodian fixture key roles")
            worker_args = [
                "--run-id", args.run_id,
                "--custodian-private-seed-file", str(args.custodian_private_seed_file),
                "--evaluator-public-key-file", str(args.evaluator_public_key_file),
                "--destination", str(args.destination),
            ]
        else:
            if (None in (args.witness_seed_file, args.enrollment_file,
                         args.evaluator_public_key_file, args.custodian_public_key_file)
                    or any(x is not None for x in (
                        args.target_seed_file, args.signing_seed_file,
                        args.custodian_private_seed_file, args.witness_public_key_file,
                        args.destination,
                    ))):
                raise ValueError("invalid witness fixture key roles")
            worker_args = [
                "--run-id", args.run_id,
                "--witness-seed-file", str(args.witness_seed_file),
                "--enrollment-file", str(args.enrollment_file),
                "--evaluator-public-key-file", str(args.evaluator_public_key_file),
                "--custodian-public-key-file", str(args.custodian_public_key_file),
            ]
        return serve_fixture(
            path=args.socket, peer_uid=args.allowed_peer_uid,
            role=args.role, arguments=worker_args,
        )
    except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired):
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
