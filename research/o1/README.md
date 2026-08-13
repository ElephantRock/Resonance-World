# O1 frozen benchmark-plane provenance

This directory records the prospectively frozen O1 (#119) benchmark provenance and exact
Plane-E/Plane-K fixture hashes. The benchmark planes themselves are **not committed** to
the repository. They are deterministically materialized during each O1 reproduction from
the exact accepted historical GitHub Actions artifacts bound in `provenance.json`.

The workflow downloads those immutable source artifacts, runs
`scripts/materialize_o1_benchmarks.py`, and verifies every generated Plane E/K file against
the hashes frozen in #119 and `provenance.json`. Plane E is then retained as the only input
to ContextGraph ingestion and reconstruction. Plane K and all raw historical artifacts are
deleted before the reconstructor runs. Only after reconstruction products have been
serialized and hashed are the exact source artifacts downloaded again and Plane K
rematerialized for evaluator-side acceptance.

The Phase-5C turnover materialization uses deterministic World routing only to recover the
runtime-selected replacement members under irreversible opaque aliases; private source
UUIDs and `practice_by_skill` never enter Plane E. The W9-06 source-sustainability
materialization similarly replays the frozen accepted runtime to produce public
market/service observations. Its 72 cycle-level service observations sum exactly to the
accepted W9-06 organization success totals. Hidden source-frontier/capability-stock
diagnostics remain evaluator-only and are explicitly classified as not observationally
identifiable from Plane E.

These fixture bytes were frozen before authoritative O1 outcome evidence. Historical
PIANO/W9 classifications remain unchanged. Any post-outcome fixture correction requires a
separately documented apparatus correction; fixtures may not be altered to rescue an O1
failure.
