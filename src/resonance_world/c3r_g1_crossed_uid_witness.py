"""One-shot offline crossed G1 witness checkpoint worker for a separate Linux UID.

Locally reproduces the enrolled Ed25519 sequence-1 receipt, signs a sequence-2
checkpoint only after verifying 16 source receipts and a custodian deposit.
This does NOT attest third-party custody, trusted time or scientific validity.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin, _digest
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_crossed_source_deposit import read_private_seed
from resonance_world.c3r_g1_crossed_witness_checkpoint import verify_witness_checkpoint
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

MAX_INPUT_BYTES = 256 * 1024


def issue_checkpoint(
    *, run_id: str, witness_seed: bytes, enrollment: dict[str, object],
    evaluator_public_hex: str, custodian_public_hex: str,
    source_receipts: tuple[dict[str, object], ...],
    custodian_deposit: dict[str, object],
    claimed_clock_utc: datetime,
) -> dict[str, object]:
    """Issue a locally signed claim after source-chain and custody checks."""
    signer = ReceiptSigner(witness_seed, run_id=run_id)
    pin = EnrollmentPin.verify(
        enrollment, pinned_witness_public_key_hex=signer.public_key_hex,
        expected_run_id=run_id,
        expected_evaluator_public_key_hex=evaluator_public_hex,
        expected_custodian_public_key_hex=custodian_public_hex,
        claimed_clock_check_utc=claimed_clock_utc,
    )
    first = signer.seal(enrollment["payload"])
    if first != enrollment:
        raise ValueError("enrollment not first signed receipt from pinned witness")
    source = verify_crossed_receipt_chain(
        make_plan(), receipts=source_receipts, mode="development",
        expected_run_id=run_id,
        pinned_evaluator_public_key_hex=evaluator_public_hex,
    )
    pin.verify_deposit(
        deposit=custodian_deposit,
        source_head_sha256=source.source_chain_head_sha256,
    )
    checkpoint = signer.seal({
        "schema": "c3r-g1-crossed-witness-checkpoint-v0.1",
        "plan_digest": pin.public_plan_digest,
        "enrollment_sha256": pin.signed_enrollment_sha256,
        "source_chain_head_sha256": source.source_chain_head_sha256,
        "custodian_receipt_sha256": _digest(custodian_deposit),
        "development_attempts": 16,
        "qualification_attempts": 24,
        "claimed_checkpoint_at_utc": claimed_clock_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "external_immutable_deposit_attested": False,
        "provider_sends_authorized": False,
        "scientific_acceptance": False,
    })
    audit = verify_witness_checkpoint(
        pin, signed_enrollment=enrollment, signed_checkpoint=checkpoint,
        signed_custodian_deposit=custodian_deposit,
        source_chain_head_sha256=source.source_chain_head_sha256,
        claimed_clock_check_utc=claimed_clock_utc,
    ).audit()
    if audit["scientific_acceptance"] is not False:
        raise ValueError("local witness must never assert scientific acceptance")
    return checkpoint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local fourth-UID witness checkpoint")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--witness-seed-file", type=Path, required=True)
    parser.add_argument("--enrollment-file", type=Path, required=True)
    parser.add_argument("--evaluator-public-key-file", type=Path, required=True)
    parser.add_argument("--custodian-public-key-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if (args.enrollment_file.is_symlink()
                or args.enrollment_file.stat().st_size > 4096):
            raise ValueError("oversized or redirected enrollment")
        enrollment = json.loads(args.enrollment_file.read_text(encoding="utf-8"))
        line = sys.stdin.buffer.readline(MAX_INPUT_BYTES + 1)
        if not line or len(line) > MAX_INPUT_BYTES:
            raise ValueError("missing or oversized witness checkpoint request")
        request = json.loads(line)
        if (not isinstance(request, dict)
                or set(request) != {"op", "source_receipts", "custodian_deposit"}
                or request["op"] != "checkpoint"
                or not isinstance(request["source_receipts"], list)
                or not isinstance(request["custodian_deposit"], dict)):
            raise ValueError("invalid checkpoint request")
        checkpoint = issue_checkpoint(
            run_id=args.run_id,
            witness_seed=read_private_seed(args.witness_seed_file),
            enrollment=enrollment,
            evaluator_public_hex=args.evaluator_public_key_file.read_text(
                encoding="ascii"
            ).strip(),
            custodian_public_hex=args.custodian_public_key_file.read_text(
                encoding="ascii"
            ).strip(),
            source_receipts=tuple(request["source_receipts"]),
            custodian_deposit=request["custodian_deposit"],
            claimed_clock_utc=datetime.now(UTC),
        )
        result = {
            "phase": "signed_local_witness_checkpoint",
            "signed_witness_checkpoint": checkpoint,
            "external_witness_attested": False,
            "trusted_timestamp_attested": False,
            "scientific_acceptance": False,
        }
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return 0
    except (ValueError, TypeError, KeyError, OSError, UnicodeError):
        sys.stdout.write(json.dumps({
            "phase": "local_witness_checkpoint_rejected",
            "scientific_acceptance": False,
        }, sort_keys=True) + "\n")
        sys.stdout.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
