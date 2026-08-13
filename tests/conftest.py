"""Project-wide pytest hooks for branch-scoped scientific reproductions."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


def pytest_sessionstart(session: object) -> None:
    if importlib.util.find_spec("resonance_contextgraph") is None:
        return
    from h2_turnover_reproduction import reproduce_h2_exact_head

    with tempfile.TemporaryDirectory(prefix="resonance-h2-") as directory:
        reproduce_h2_exact_head(Path(directory))
