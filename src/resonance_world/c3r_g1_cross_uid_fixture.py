"""A zero-provider G1 cross-UID client for disposable Linux CI only.

It accepts ONLY a pinned evaluator public key and Unix socket; no evaluator
private seed, provider secret, billing configuration or network model calls.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .c3r_g1_evaluator_receipts import (
    ReceiptVerifier,
    VerifiedEvaluatorSession,
)
from .c3r_g1_evaluator_transcript import audit_signed_transcript
from .c3r_g1_evaluator_unix import UnixEvaluatorClient
from .c3r_g1_model_boundary import ModelChoiceCompletion
from .c3r_g1_multischema import V2Design
from .c3r_g1_sealed_runner import SealedPilotRunner


class ConstantOfflinePort:
    def complete(self, _request):
        return ModelChoiceCompletion("A", "offline-schema-fixture")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-UID offline G1 client fixture")
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-evaluator-uid", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        own_uid = os.geteuid()
        info = args.socket.stat()
        if own_uid == 0 or own_uid == args.expected_evaluator_uid:
            raise ValueError("agent UID must differ from evaluator UID and root")
        if info.st_uid != args.expected_evaluator_uid:
            raise ValueError("socket ownership does not match pinned evaluator UID")
        if info.st_mode & 0o002:
            raise ValueError("evaluator socket cannot be world writable")
        public_hex = args.public_key.read_text(encoding="ascii").strip()
        design = V2Design(
            units=1, development_per_family=1, qualification_per_family=1,
        )
        cohort = design.freeze()
        with UnixEvaluatorClient(args.socket) as transport:
            session = VerifiedEvaluatorSession(
                transport, ReceiptVerifier(public_hex, expected_run_id=args.run_id)
            )
            result = SealedPilotRunner(cohort, session).run(
                port_factory=lambda _unit, _arm, _stage: ConstantOfflinePort(),
            )
            audit = audit_signed_transcript(
                list(session.signed_receipts), cohort,
                public_key_hex=public_hex, expected_run_id=args.run_id,
            )
        if (audit.status != "signed_structurally_consistent"
                or audit.signed_attempts != design.logical_calls
                or result.to_dict()["scientific_acceptance"] is not False):
            raise ValueError("offline cross-UID cohort verification failed")
    except (ValueError, OSError, TimeoutError):
        print(json.dumps({
            "status": "cross_uid_fixture_rejected",
            "scientific_acceptance": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "schema": "c3r-g1-cross-uid-fixture-v0.1",
        "status": "cross_uid_signed_protocol_pass",
        "agent_uid": own_uid,
        "evaluator_uid": args.expected_evaluator_uid,
        "signed_attempts": audit.signed_attempts,
        "independent_operator_attested": False,
        "provider_sends_verified": False,
        "scientific_acceptance": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
