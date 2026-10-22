"""Agent-UID-only G1 crossed offline fixture client; no provider transport.

Talks to evaluator and custodian sockets. Reads pinned PUBLIC keys only.
Uses deterministic dummy A/B actions, not model outputs or scientific data.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
from datetime import UTC, datetime
import stat
import struct
from pathlib import Path
from typing import TextIO

from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain

MAX_REPLY_BYTES = 160 * 1024


def _connect(path: Path, *, expected_server_uid: int) -> socket.socket:
    """Require kernel-backed peer UID, not an untrusted application claim."""
    if (not hasattr(socket, "SO_PEERCRED")
            or type(expected_server_uid) is not int or expected_server_uid < 1
            or path.is_symlink()):
        raise ValueError("Linux pinned service identity required")
    info = path.stat()
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != expected_server_uid
            or info.st_mode & 0o002):
        raise ValueError("socket file not owned by pinned service UID")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(20)
    try:
        sock.connect(str(path))
        packed = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                 struct.calcsize("3i"))
        _pid, peer_uid, _gid = struct.unpack("3i", packed)
        if peer_uid != expected_server_uid:
            raise ValueError("server peer credentials failed UID verification")
        return sock
    except Exception:
        sock.close()
        raise


def _send(reader: TextIO, writer: TextIO, request: dict[str, object]) -> dict:
    writer.write(json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n")
    writer.flush()
    line = reader.readline(MAX_REPLY_BYTES + 1)
    if not line or len(line) > MAX_REPLY_BYTES:
        raise ValueError("missing or oversized offline fixture response")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("fixture response must be an object")
    return value


def run_fixture(*, evaluator_socket: Path, custodian_socket: Path,
                evaluator_uid: int, custodian_uid: int,
                evaluator_public_key_hex: str, custodian_public_key_hex: str,
                run_id: str, enrollment_pin: EnrollmentPin | None = None
                ) -> dict[str, object]:
    """Cross-UID toy exercise; source-grade and holdout-receipt isolation."""
    me = os.geteuid()
    if 0 in (me, evaluator_uid, custodian_uid) or len({
            me, evaluator_uid, custodian_uid}) != 3:
        raise ValueError("three different unprivileged OS identities required")
    plan = make_plan()
    if (enrollment_pin is None or enrollment_pin.run_id != run_id
            or enrollment_pin.public_plan_digest != plan.public_digest
            or enrollment_pin.evaluator_public_key_hex != evaluator_public_key_hex
            or enrollment_pin.custodian_public_key_hex != custodian_public_key_hex):
        raise ValueError("valid prospective witness enrollment required before source")
    with _connect(evaluator_socket, expected_server_uid=evaluator_uid) as eva:
        reader = eva.makefile("r", encoding="utf-8")
        writer = eva.makefile("w", encoding="utf-8")
        try:
            ready_line = reader.readline(MAX_REPLY_BYTES + 1)
            ready = json.loads(ready_line)
            if (ready.get("phase") != "source"
                    or ready.get("evaluator_public_key_hex") != evaluator_public_key_hex
                    or ready.get("public_plan_digest") != plan.public_digest
                    or ready.get("actual_provider_sends") != 0):
                raise ValueError("evaluator ready inconsistent with prior pinned key or plan")
            source = []
            for i in range(16):
                reply = _send(reader, writer, {
                    "op": "submit", "status": "accepted", "choice": "A",
                })
                if (reply.get("phase") != "development_feedback"
                        or reply.get("source_received") != i + 1
                        or type(reply.get("feedback")) is not bool
                        or not isinstance(reply.get("signed_source_receipt"), dict)):
                    raise ValueError("source feedback missing or malformed")
                source.append(reply["signed_source_receipt"])
            verified = verify_crossed_receipt_chain(
                plan, receipts=tuple(source), mode="development",
                expected_run_id=run_id,
                pinned_evaluator_public_key_hex=evaluator_public_key_hex,
            )
            freeze = _send(reader, writer, {"op": "seal_source"})
            if (freeze.get("phase") != "await_source_custody"
                    or freeze.get("source_chain_head_sha256")
                    != verified.source_chain_head_sha256):
                raise ValueError("source freeze did not match signed transcript")
            with _connect(custodian_socket, expected_server_uid=custodian_uid) as custody:
                cust_reader = custody.makefile("r", encoding="utf-8")
                cust_writer = custody.makefile("w", encoding="utf-8")
                try:
                    reply = _send(cust_reader, cust_writer, {
                        "op": "deposit", "source_receipts": source,
                    })
                finally:
                    cust_writer.close()
                    cust_reader.close()
            if reply.get("phase") != "source_custody_claim_signed_locally":
                raise ValueError("custodian did not sign a valid source deposit")
            deposit = reply.get("signed_custody_receipt")
            checked_deposit = enrollment_pin.verify_deposit(
                deposit=deposit, source_head_sha256=verified.source_chain_head_sha256,
            )
            if not checked_deposit["source_deposit_signed_by_registered_custodian"]:
                raise ValueError("prospectively pinned source custodian rejected")
            opened = _send(reader, writer, {
                "op": "acknowledge_custody", "deposit": deposit,
            })
            if opened.get("phase") != "qualification_allowed_by_local_signed_custody_claim":
                raise ValueError("qualification gate did not require signed custody")
            for i in range(24):
                # Last logical slot deliberately unresolved to test accounting.
                status = "accepted" if i < 23 else "not_sent"
                response = _send(reader, writer, {
                    "op": "submit", "status": status,
                    "choice": "B" if status == "accepted" else None,
                })
                if (set(response) != {"schema", "phase", "qualification_received"}
                        or response["phase"] != "qualification_sealed"
                        or response["qualification_received"] != i + 1):
                    raise ValueError("holdout grade or signed result leaked before closure")
            final = _send(reader, writer, {"op": "finalize"})
            terminal = enrollment_pin.verify_terminal(
                receipts=tuple(final["receipts"]),
                expected_source_head_sha256=verified.source_chain_head_sha256,
            )
            if (final.get("actual_provider_sends") != 0
                    or final.get("scientific_acceptance") is not False
                    or final.get("source_chain_head_sha256")
                    != verified.source_chain_head_sha256
                    or terminal["verified_logical_attempts"] != 40
                    or not terminal["source_chain_digest_locked"]):
                raise ValueError("terminal evidence audit diverged")
            return {
                "schema": "c3r-g1-crossed-three-uid-offline-fixture-v0.1",
                "verdict": "three_uid_signed_local_fixture_pass_not_attested",
                "agent_uid": me,
                "evaluator_uid": evaluator_uid,
                "custodian_uid": custodian_uid,
                "signed_source_attempts": 16,
                "signed_total_logical_attempts": 40,
                "qualification_grade_released_before_closure": False,
                "source_deposit_binds_chain_head": True,
                "pre_source_witness_enrollment_checked": True,
                "enrollment_sha256": enrollment_pin.signed_enrollment_sha256,
                "independent_witness_attested": False,
                "local_custodian_operator_independent": False,
                "external_custody_verified": False,
                "provider_sends": 0,
                "scientific_acceptance": False,
            }
        finally:
            writer.close()
            reader.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crossed G1 third UID offline client")
    parser.add_argument("--evaluator-socket", type=Path, required=True)
    parser.add_argument("--custodian-socket", type=Path, required=True)
    parser.add_argument("--evaluator-uid", type=int, required=True)
    parser.add_argument("--custodian-uid", type=int, required=True)
    parser.add_argument("--evaluator-public-key-file", type=Path, required=True)
    parser.add_argument("--custodian-public-key-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--witness-public-key-file", type=Path, required=True)
    parser.add_argument("--enrollment-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        eval_pub = args.evaluator_public_key_file.read_text(encoding="ascii").strip()
        cust_pub = args.custodian_public_key_file.read_text(encoding="ascii").strip()
        if (args.enrollment_file.is_symlink()
                or args.enrollment_file.stat().st_size > 4096):
            raise ValueError("missing or oversized prospective enrollment")
        enrollment = json.loads(args.enrollment_file.read_text(encoding="utf-8"))
        pin = EnrollmentPin.verify(
            enrollment,
            pinned_witness_public_key_hex=args.witness_public_key_file.read_text(
                encoding="ascii"
            ).strip(),
            expected_run_id=args.run_id,
            expected_evaluator_public_key_hex=eval_pub,
            expected_custodian_public_key_hex=cust_pub,
            claimed_clock_check_utc=datetime.now(UTC),
        )
        result = run_fixture(
            evaluator_socket=args.evaluator_socket,
            custodian_socket=args.custodian_socket,
            evaluator_uid=args.evaluator_uid,
            custodian_uid=args.custodian_uid,
            evaluator_public_key_hex=args.evaluator_public_key_file.read_text(
                encoding="ascii"
            ).strip(),
            custodian_public_key_hex=args.custodian_public_key_file.read_text(
                encoding="ascii"
            ).strip(),
            run_id=args.run_id, enrollment_pin=pin,
        )
    except (ValueError, OSError, KeyError, TypeError, UnicodeError, TimeoutError):
        print(json.dumps({
            "verdict": "crossed_three_uid_fixture_rejected",
            "scientific_acceptance": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
