"""Read-only SQL observer used by the W0 non-interference experiment."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

_QUERY = """
SELECT
  (SELECT COUNT(*) FROM decision_events) AS decision_events,
  (SELECT COUNT(*) FROM traces) AS traces,
  (SELECT COUNT(*) FROM market_tasks) AS market_tasks,
  (SELECT COUNT(*) FROM experiment_snapshots) AS experiment_snapshots
"""


def observe(
    dsn: str,
    *,
    stop_file: str | Path,
    output_path: str | Path,
    interval_seconds: float = 0.10,
    max_seconds: float = 120.0,
) -> dict[str, Any]:
    """Poll Field state read-only until ``stop_file`` exists or timeout expires."""

    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    if max_seconds <= 0:
        raise ValueError("max_seconds must be positive")

    import psycopg
    from psycopg.rows import dict_row

    stop = Path(stop_file)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    query_seconds = 0.0
    attempts = 0
    successful_snapshots = 0
    last_counts: dict[str, int] = {}

    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        connection.execute("SET default_transaction_read_only = on")
        while not stop.exists() and time.perf_counter() - started < max_seconds:
            attempts += 1
            query_started = time.perf_counter()
            try:
                row = connection.execute(_QUERY).fetchone()
            except Exception:
                row = None
            query_seconds += time.perf_counter() - query_started

            if row is not None:
                successful_snapshots += 1
                last_counts = {key: int(value) for key, value in row.items()}

            elapsed = time.perf_counter() - query_started
            time.sleep(max(0.0, interval_seconds - elapsed))

    payload = {
        "attempts": attempts,
        "elapsed_seconds": time.perf_counter() - started,
        "interval_seconds": interval_seconds,
        "last_counts": last_counts,
        "query_seconds": query_seconds,
        "successful_snapshots": successful_snapshots,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--stop-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=0.10)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    args = parser.parse_args(argv)
    payload = observe(
        args.dsn,
        stop_file=args.stop_file,
        output_path=args.output,
        interval_seconds=args.interval,
        max_seconds=args.max_seconds,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
