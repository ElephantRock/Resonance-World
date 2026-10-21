"""Tiny opt-in live technical qualification: maximum EIGHT physical requests.

No provider call occurs in dry-run mode (the default). This is not a powered
G1 study and must never be entered in the scientific evidence registry.
"""

from __future__ import annotations

import argparse
import json
import os

from resonance_world.c3r_g1_model_boundary import ModelCohortLock, ModelG1Runner
from resonance_world.c3r_g1_zai_transport import (
    MAX_TOTAL_SENDS,
    PhysicalSendLedger,
    ZaiStandardModelPort,
)
from resonance_world.c3r_g2_probe import FixtureOracle, make_task

CONTEXT = "c3r-source-smoke-1"
EXPECTED_SENDS = 8


def make_smoke_cohort() -> ModelCohortLock:
    # Local technical probe only: fixed operands and evaluation law.
    return ModelCohortLock(
        development=tuple(
            make_task(split="dev", context=CONTEXT, number=n) for n in range(4)
        ),
        qualification=tuple(
            make_task(split="holdout", context=CONTEXT, number=n) for n in range(2)
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="C3R technical qualification; dry-run unless explicitly live"
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-sends", type=int, default=EXPECTED_SENDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.max_sends != EXPECTED_SENDS or EXPECTED_SENDS > MAX_TOTAL_SENDS:
        raise SystemExit("C3R smoke uses exactly eight reserved physical sends")
    cohort = make_smoke_cohort()
    if not args.live:
        print(
            json.dumps(
                {
                    "schema": "c3r-live-qualification-preflight-v0.1",
                    "status": "offline_preflight_no_sends",
                    "cohort_digest": cohort.digest,
                    "physical_send_limit": EXPECTED_SENDS,
                    "provider_endpoint": "pinned_standard_api_only",
                    "model": args.model,
                    "requires_live_opt_in": True,
                    "requires_env_key": "C3R_ZAI_API_KEY",
                    "scientific_acceptance": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if not args.model or not args.model.strip():
        raise SystemExit("live C3R qualification requires an explicit model id")
    api_key = os.environ.get("C3R_ZAI_API_KEY", "")
    if not api_key.strip():
        raise SystemExit("C3R_ZAI_API_KEY must be provided privately in the environment")

    ledger = PhysicalSendLedger(max_total_sends=EXPECTED_SENDS)
    # Port is enabled only inside this explicit-live CLI. One shared ledger
    # covers development, trained qualification and fresh qualification.
    port = ZaiStandardModelPort(
        api_key=api_key,
        model_id=args.model,
        ledger=ledger,
        enabled=True,
    )
    outcome = ModelG1Runner(
        oracle=FixtureOracle({CONTEXT: ("multiply", "add")}),
        cohort=cohort,
    ).execute(owner_id="source-smoke", learned_port=port, fresh_port=port)
    print(
        json.dumps(
            {
                "schema": "c3r-live-technical-qualification-v0.1",
                "status": "technical_smoke_not_scientific_evidence",
                "cohort_digest": cohort.digest,
                "model": args.model,
                "report": outcome.to_dict(),
                "send_ledger": ledger.to_dict(),
                "scientific_acceptance": False,
            },
            sort_keys=True, separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
