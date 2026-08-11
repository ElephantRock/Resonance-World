"""Production-parity entry point for the W8 native replacement assay."""

from __future__ import annotations

from collections.abc import Sequence

from . import w8_native_replacement as native


def main(argv: Sequence[str] | None = None) -> int:
    # These are the same runtime corrections installed by Field's lifecycle_step_cli.
    # Imports stay deferred so ordinary World tests remain independent of a Field checkout.
    from resonance.experiments.lifecycle_corrections import install_lifecycle_corrections
    from resonance.experiments.lifecycle_retrieval import install_diversified_retrieval_fix

    install_lifecycle_corrections()
    install_diversified_retrieval_fix()
    return native.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
