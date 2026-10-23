"""Staged fourth G1 evaluator *fixture*, with a local subprocess CLI.

Private target labels and Ed25519 signing keys stay on the evaluator side of
this fixture protocol. Same-UID subprocess execution is NOT a hardened trust
boundary, independent evaluator or authenticated provider send.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin
from resonance_world.c3r_g1_crossed_internal_lock import (
    verify_internal_source_lock,
    write_internal_source_lock,
)
from resonance_world.c3r_g1_crossed_plan import evaluator_private_assignment, make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_crossed_source_deposit import (
    read_private_seed,
    verify_source_deposit,
)
from resonance_world.c3r_g1_crossed_witness_checkpoint import (
    WitnessCheckpoint,
    verify_witness_checkpoint,
)
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

MAX_INBOUND = 4096
MAX_MESSAGES = 44


class CrossedLocalEvaluator:
    """Fail-closed 16-source / deposit / 24-holdout offline staged protocol."""

    def __init__(
        self, *, run_id: str, private_target_seed: bytes,
        signing_seed: bytes, pinned_custodian_public_key_hex: str | None = None,
        internal_checkpoint_dir: Path | None = None,
        signed_enrollment: dict[str, object] | None = None,
        pinned_witness_public_key_hex: str | None = None,
        claimed_clock_check_utc: datetime | None = None,
    ) -> None:
        self._plan = make_plan()
        self._targets = evaluator_private_assignment(
            self._plan, secret=private_target_seed,
        )
        self._signer = ReceiptSigner(signing_seed, run_id=run_id)
        self._run_id = run_id
        self._custodian_pin = pinned_custodian_public_key_hex
        self._internal_checkpoint_dir = internal_checkpoint_dir
        self._internal_source_lock_sha256: str | None = None
        if internal_checkpoint_dir is not None:
            if pinned_custodian_public_key_hex is not None:
                raise ValueError("internal mode cannot depend on a custodian")
            if any(v is not None for v in (
                signed_enrollment, pinned_witness_public_key_hex, claimed_clock_check_utc,
            )):
                raise ValueError("internal mode cannot depend on a witness")
        elif not pinned_custodian_public_key_hex:
            raise ValueError("signed custody mode requires custodian key")
        if self._signer.public_key_hex == pinned_custodian_public_key_hex:
            raise ValueError("custodian must not share evaluator signing key")
        self._records: list[dict[str, object]] = []
        self._source_head: str | None = None
        self._custody_accepted = False
        self._finished = False
        self._witness_checkpoint: WitnessCheckpoint | None = None
        self._witness_enrollment = signed_enrollment
        self._witness_pin: EnrollmentPin | None = None
        self._claimed_clock_check_utc = claimed_clock_check_utc
        witness_inputs = (signed_enrollment, pinned_witness_public_key_hex,
                          claimed_clock_check_utc)
        if any(value is not None for value in witness_inputs):
            if any(value is None for value in witness_inputs):
                raise ValueError("witness enrollment requires all pre-source pins")
            self._witness_pin = EnrollmentPin.verify(
                signed_enrollment,
                pinned_witness_public_key_hex=pinned_witness_public_key_hex,
                expected_run_id=run_id,
                expected_evaluator_public_key_hex=self.evaluator_public_key_hex,
                expected_custodian_public_key_hex=pinned_custodian_public_key_hex,
                claimed_clock_check_utc=claimed_clock_check_utc,
            )

    @property
    def evaluator_public_key_hex(self) -> str:
        return self._signer.public_key_hex

    def ready(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-crossed-local-evaluator-v0.1",
            "phase": "source",
            "public_plan_digest": self._plan.public_digest,
            "source_attempts": 16,
            "qualification_attempts": 24,
            "evaluator_public_key_hex": self.evaluator_public_key_hex,
            "actual_provider_sends": 0,
            "scientific_acceptance": False,
        }

    def submit(self, *, status: str, choice: str | None) -> dict[str, object]:
        if self._finished or len(self._records) >= 40:
            raise ValueError("crossed evaluator already finished prescribed attempts")
        index = len(self._records)
        if index == 16 and not self._custody_accepted:
            if self._internal_checkpoint_dir is not None:
                raise ValueError("holdout prohibited before source lock")
            raise ValueError("holdout prohibited before signed source custody acknowledgement")
        if index == 16 and self._internal_checkpoint_dir is not None:
            self._check_internal_source_lock()
        if (status not in ("accepted", "invalid_format", "provider_error", "not_sent")
                or (status == "accepted" and choice not in ("A", "B"))
                or (status != "accepted" and choice is not None)):
            raise ValueError("invalid reported action and status combination")
        slot = self._plan.schedule[index]
        cell = next(c for c in self._plan.cells if c.unit_id == slot.unit_id)
        task = next(t for t in (*cell.development, *cell.qualification)
                    if t.task_id == slot.task_id)
        # Stand-in accepted A/B action, NOT a real model/provider response.
        score = choice == self._targets[task.context_id] if status == "accepted" else None
        output_sha = hashlib.sha256(choice.encode()).hexdigest() if choice else None
        body = {
            "schema": "c3r-g1-crossed-attempt-v0.1",
            "plan_digest": self._plan.public_digest,
            "slot_index": index,
            "unit_id": slot.unit_id,
            "task_id": slot.task_id,
            "stage": slot.stage,
            "arm": slot.arm,
            "status": status,
            "action": choice,
            "correct": score,
            "output_sha256": output_sha,
        }
        envelope = self._signer.seal(body)
        self._records.append(envelope)
        if slot.stage == "development":
            # The learned arm may receive graded source actions and signed receipts.
            return {
                "schema": "c3r-g1-crossed-local-response-v0.1",
                "phase": "development_feedback",
                "source_received": len(self._records),
                "feedback": score,
                "signed_source_receipt": envelope,
            }
        # Holdout correctness, target and signed outcome are withheld until
        # all 24 qualification attempts have closed.
        return {
            "schema": "c3r-g1-crossed-local-response-v0.1",
            "phase": "qualification_sealed",
            "qualification_received": len(self._records) - 16,
        }

    def _check_internal_source_lock(self) -> None:
        if (self._internal_checkpoint_dir is None
                or self._internal_source_lock_sha256 is None):
            raise ValueError("no internal source lock is recorded")
        verify_internal_source_lock(
            directory=self._internal_checkpoint_dir, run_id=self._run_id,
            evaluator_public_key_hex=self.evaluator_public_key_hex,
            source_receipts=tuple(self._records[:16]),
            expected_lock_sha256=self._internal_source_lock_sha256,
        )

    def seal_source(self) -> dict[str, object]:
        if self._finished or len(self._records) != 16 or self._source_head is not None:
            raise ValueError("source must be sealed once after exactly sixteen attempts")
        checked = verify_crossed_receipt_chain(
            self._plan, receipts=tuple(self._records), mode="development",
            expected_run_id=self._run_id,
            pinned_evaluator_public_key_hex=self.evaluator_public_key_hex,
        )
        if self._internal_checkpoint_dir is not None:
            _record, sha = write_internal_source_lock(
                directory=self._internal_checkpoint_dir, run_id=self._run_id,
                evaluator_public_key_hex=self.evaluator_public_key_hex,
                source_receipts=tuple(self._records),
            )
            self._internal_source_lock_sha256 = sha
            self._custody_accepted = True
        self._source_head = checked.source_chain_head_sha256
        return {
            "schema": "c3r-g1-crossed-local-response-v0.1",
            "phase": (
                "internal_source_frozen_qualification_allowed"
                if self._internal_checkpoint_dir is not None
                else "await_source_custody"
            ),
            "source_chain_head_sha256": self._source_head,
            "source_receipt_count": 16,
            "internal_source_lock_sha256": self._internal_source_lock_sha256,
            "custodian_independence_attested": False,
            "scientific_acceptance": False,
        }

    def acknowledge_custody(
        self, deposit: dict[str, object], *,
        witness_checkpoint: dict[str, object] | None = None,
        claimed_clock_check_utc: datetime | None = None,
    ) -> dict[str, object]:
        if self._internal_checkpoint_dir is not None:
            raise ValueError("internal mode has no custodian approval step")
        if (self._source_head is None or self._custody_accepted
                or len(self._records) != 16 or self._finished):
            raise ValueError("custody must be acknowledged exactly once before holdout")
        if self._witness_pin is None and witness_checkpoint is not None:
            raise ValueError("witness checkpoint requires pre-source enrollment")
        verify_source_deposit(
            deposit=deposit, source_head=self._source_head,
            expected_run_id=self._run_id,
            evaluator_public_key_hex=self.evaluator_public_key_hex,
            pinned_custodian_public_key_hex=self._custodian_pin,
        )
        if self._witness_pin is not None:
            if witness_checkpoint is None:
                raise ValueError("registered witness checkpoint required before holdout")
            self._witness_checkpoint = verify_witness_checkpoint(
                self._witness_pin,
                signed_enrollment=self._witness_enrollment,
                signed_checkpoint=witness_checkpoint,
                signed_custodian_deposit=deposit,
                source_chain_head_sha256=self._source_head,
                claimed_clock_check_utc=(
                    claimed_clock_check_utc
                    if claimed_clock_check_utc is not None
                    else self._claimed_clock_check_utc
                ),
            )
        self._custody_accepted = True
        return {
            "schema": "c3r-g1-crossed-local-response-v0.1",
            "phase": "qualification_allowed_by_local_signed_custody_claim",
            "external_independence_attested": False,
            "scientific_acceptance": False,
        }

    def finalize(self) -> dict[str, object]:
        if not self._custody_accepted or self._finished or len(self._records) != 40:
            raise ValueError("qualification cannot finalize before full 40-slot closure")
        if self._internal_checkpoint_dir is not None:
            self._check_internal_source_lock()
        checked = verify_crossed_receipt_chain(
            self._plan, receipts=tuple(self._records), mode="terminal",
            expected_run_id=self._run_id,
            pinned_evaluator_public_key_hex=self.evaluator_public_key_hex,
            expected_source_chain_head_sha256=self._source_head,
        )
        self._finished = True
        return {
            "schema": "c3r-g1-crossed-local-final-v0.1",
            "phase": "completed_local_fixture_only",
            "receipts": self._records,
            "source_chain_head_sha256": self._source_head,
            "audit": checked.audit,
            "actual_provider_sends": 0,
            "source_gate_mode": (
                "internal_durable_checkpoint" if self._internal_checkpoint_dir is not None
                else "signed_custodian_witness"
            ),
            "internal_source_lock_sha256": self._internal_source_lock_sha256,
            "requires_external_approval": False,
            "prospective_witness_checkpoint_checked": self._witness_checkpoint is not None,
            "witness_checkpoint_sha256": (
                self._witness_checkpoint.witness_checkpoint_sha256
                if self._witness_checkpoint is not None else None
            ),
            "scientific_acceptance": False,
        }


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1 crossed zero-provider evaluator subprocess")
    parser.add_argument("--target-seed-file", required=True, type=Path)
    parser.add_argument("--signing-seed-file", required=True, type=Path)
    parser.add_argument("--custodian-public-key-file", type=Path)
    parser.add_argument("--internal-checkpoint-dir", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--enrollment-file", type=Path)
    parser.add_argument("--witness-public-key-file", type=Path)
    args = parser.parse_args(argv)
    try:
        if (args.internal_checkpoint_dir is None) == (
            args.custodian_public_key_file is None
        ):
            raise ValueError("select exactly one internal checkpoint or custodian mode")
        if (args.internal_checkpoint_dir is not None
                and (args.enrollment_file is not None
                     or args.witness_public_key_file is not None)):
            raise ValueError("internal mode cannot block on witness enrollment")
        if (args.enrollment_file is None) != (args.witness_public_key_file is None):
            raise ValueError("witness enrollment and public key must be specified together")
        enrollment = None
        witness_key = None
        local_clock = None
        if args.enrollment_file is not None:
            if (args.enrollment_file.is_symlink()
                    or args.enrollment_file.stat().st_size > 4096):
                raise ValueError("witness enrollment file is redirected or oversized")
            enrollment = json.loads(args.enrollment_file.read_text(encoding="utf-8"))
            witness_key = args.witness_public_key_file.read_text(
                encoding="ascii"
            ).strip()
            local_clock = datetime.now(UTC)
        engine = CrossedLocalEvaluator(
            run_id=args.run_id,
            private_target_seed=read_private_seed(args.target_seed_file),
            signing_seed=read_private_seed(args.signing_seed_file),
            pinned_custodian_public_key_hex=(
                args.custodian_public_key_file.read_text(encoding="ascii").strip()
                if args.custodian_public_key_file is not None else None
            ),
            internal_checkpoint_dir=args.internal_checkpoint_dir,
            signed_enrollment=enrollment,
            pinned_witness_public_key_hex=witness_key,
            claimed_clock_check_utc=local_clock,
        )
        _emit(engine.ready())
        for _ in range(MAX_MESSAGES):
            line = sys.stdin.buffer.readline(MAX_INBOUND + 1)
            if not line or len(line) > MAX_INBOUND:
                raise ValueError("client stream ended or exceeded request budget")
            obj = json.loads(line)
            if not isinstance(obj, dict) or not isinstance(obj.get("op"), str):
                raise ValueError("malformed evaluator command")
            op = obj["op"]
            if op == "submit" and set(obj) == {"op", "status", "choice"}:
                response = engine.submit(status=obj["status"], choice=obj["choice"])
            elif op == "seal_source" and set(obj) == {"op"}:
                response = engine.seal_source()
            elif op == "acknowledge_custody" and set(obj) in (
                {"op", "deposit"}, {"op", "deposit", "witness_checkpoint"},
            ):
                response = engine.acknowledge_custody(
                    obj["deposit"], witness_checkpoint=obj.get("witness_checkpoint"),
                    claimed_clock_check_utc=(
                        datetime.now(UTC) if "witness_checkpoint" in obj else None
                    ),
                )
            elif op == "finalize" and set(obj) == {"op"}:
                _emit(engine.finalize())
                return 0
            else:
                raise ValueError("unsupported crossed evaluator command")
            _emit(response)
        raise ValueError("crossed evaluator message limit exceeded")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        _emit({"status": "offline_evaluator_rejected", "scientific_acceptance": False})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
