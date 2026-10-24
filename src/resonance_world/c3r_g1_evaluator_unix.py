"""Linux Unix-socket transport for a separately owned G1 evaluator process.

The evaluator key stays on the server side. Peer identity is checked by the
Linux kernel via SO_PEERCRED, not an untrusted string in a JSON request.
This is an engineering deployment boundary, not evaluator independence proof.
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
from typing import TextIO

from .c3r_g1_sealed_runner import JsonLineEvaluatorSession

MAX_REJECTED_PEERS = 16


def _check_socket_directory(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("socket path must be absolute")
    if len(os.fsencode(path)) >= 104:
        raise ValueError("Unix socket path too long")
    parent = path.parent
    info = parent.stat()
    if (not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o022):
        raise ValueError("socket parent must be owned by server and not group/world writable")
    if path.exists() or path.is_symlink():
        raise ValueError("refusing to overwrite existing Unix socket path")


def serve_once(
    socket_path: Path, *, allowed_peer_uid: int,
    worker_arguments: list[str],
) -> int:
    """Serve exactly one allowed client. Does not log raw worker contents."""
    if (not hasattr(socket, "SO_PEERCRED") or type(allowed_peer_uid) is not int
            or allowed_peer_uid < 0):
        raise ValueError("Linux peer credentials and a pinned UID are required")
    _check_socket_directory(socket_path)
    original_umask = os.umask(0o117)
    try:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(str(socket_path))
        finally:
            os.umask(original_umask)
        try:
            os.chmod(socket_path, 0o660)
            server.listen(1)
            server.settimeout(30)
            for _ in range(MAX_REJECTED_PEERS):
                client, _ = server.accept()
                try:
                    packed = client.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
                    )
                    _pid, uid, _gid = struct.unpack("3i", packed)
                    if uid != allowed_peer_uid:
                        continue
                    command = [
                        sys.executable, "-m", "resonance_world.c3r_g1_evaluator_worker",
                        *worker_arguments,
                    ]
                    # The private grader key is opened by the child under
                    # the evaluator's OS identity, never by this client.
                    result = subprocess.run(
                        command, stdin=client, stdout=client,
                        stderr=subprocess.DEVNULL, timeout=120, check=False,
                    )
                    return result.returncode
                finally:
                    client.close()
            return 2
        finally:
            server.close()
    finally:
        if socket_path.exists() and stat.S_ISSOCK(socket_path.lstat().st_mode):
            socket_path.unlink()


class UnixEvaluatorClient:
    """One socket connection with the same bounded JSONL request interface."""

    def __init__(self, path: Path, *, timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("client deadline must be bounded")
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.settimeout(timeout_seconds)
        try:
            self._socket.connect(str(path))
            self._reader: TextIO = self._socket.makefile("r", encoding="utf-8")
            self._writer: TextIO = self._socket.makefile("w", encoding="utf-8")
            self._wire = JsonLineEvaluatorSession(self._reader, self._writer)
        except Exception:
            self._socket.close()
            raise

    def ready(self):
        return self._wire.ready()

    def submit(self, request: dict[str, object]):
        return self._wire.submit(request)

    def finalize(self):
        return self._wire.finalize()

    def close(self) -> None:
        self._writer.close()
        self._reader.close()
        self._socket.close()

    def __enter__(self) -> UnixEvaluatorClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot UID-gated G1 evaluator")
    parser.add_argument("--socket-path", type=Path, required=True)
    parser.add_argument("--allowed-peer-uid", type=int, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--signing-key-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--units", type=int, default=8)
    parser.add_argument("--development", type=int, default=6)
    parser.add_argument("--qualification", type=int, default=8)
    parser.add_argument("--public-seed", type=int, default=20261022)
    parser.add_argument("--model-id", default="offline-schema-fixture")
    args = parser.parse_args(argv)
    worker_args = [
        "--key-file", str(args.key_file),
        "--signing-key-file", str(args.signing_key_file),
        "--run-id", args.run_id,
        "--units", str(args.units),
        "--development", str(args.development),
        "--qualification", str(args.qualification),
        "--public-seed", str(args.public_seed),
        "--model-id", args.model_id,
    ]
    try:
        return serve_once(
            args.socket_path, allowed_peer_uid=args.allowed_peer_uid,
            worker_arguments=worker_args,
        )
    except (ValueError, OSError, subprocess.TimeoutExpired):
        # No private metadata, key paths or raw model content in output.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
