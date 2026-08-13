"""Project-wide pytest hooks for branch-scoped scientific reproductions."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


def pytest_sessionstart(session: object) -> None:
    if importlib.util.find_spec("resonance_contextgraph") is None:
        return
    helper_path = Path(__file__).with_name("h2_turnover_reproduction.py")
    spec = importlib.util.spec_from_file_location("h2_turnover_reproduction", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load H2 reproduction helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="resonance-h2-") as directory:
        module.reproduce_h2_exact_head(Path(directory))
