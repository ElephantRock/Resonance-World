"""Production-parity entry point for the W8 native replacement assay."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from . import w8_native_replacement as native


def main(argv: Sequence[str] | None = None) -> int:
    # These are the same runtime corrections installed by Field's lifecycle_step_cli.
    # Imports stay deferred so ordinary World tests remain independent of a Field checkout.
    from resonance.experiments import lifecycle_campaign as lc
    from resonance.experiments import lifecycle_corrections as corrections
    from resonance.experiments.lifecycle_retrieval import install_diversified_retrieval_fix

    corrections.install_lifecycle_corrections()
    install_diversified_retrieval_fix()

    # The corrected Field runner calls corrections.corrected_should_exit() directly,
    # while the W8 assay temporarily swaps lc.should_exit for its registered targeted
    # vacancy schedule. Bridge the direct corrected-runner call through lc.should_exit.
    # Outside each W8 _run_one intervention lc.should_exit is still Field's original
    # corrected exit function, so production semantics are unchanged.
    original_corrected_exit = corrections.corrected_should_exit

    def bridged_corrected_exit(
        spec: Any,
        *,
        seed: int,
        cycle: int,
        slot: int,
        born_cycle: int,
    ) -> bool:
        return bool(
            lc.should_exit(
                spec,
                seed=seed,
                cycle=cycle,
                slot=slot,
                born_cycle=born_cycle,
            )
        )

    corrections.corrected_should_exit = bridged_corrected_exit
    try:
        return native.main(argv)
    finally:
        corrections.corrected_should_exit = original_corrected_exit


if __name__ == "__main__":
    raise SystemExit(main())
