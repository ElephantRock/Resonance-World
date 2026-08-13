# O2 pre-outcome apparatus lock

This directory records the benchmark lock for O2 (#122), the final observer-only Observatory characterization stage before any Historical Substrate treatment.

The O2 corpus is generated deterministically from `scripts/materialize_o2_benchmarks.py`. The exact generator revision is `dd1fdc9836f08478db70cff2b732d74eacdde4cf`, based on frozen World `main` `28796c01c26a93e718da7de2ab01185cb2982cbd`.

The registered corpus contains 10 semantic aggregate-collision templates, four deterministic opaque relabelings per template, 40 collision pairs, and 80 longitudinal histories. Each history produces Plane E admissible evidence, Plane K evaluator truth, an R0 endpoint aggregate representation, and an R1 flat chronological log. The materializer fails if any registered R0 twin pair is not byte-identical or if the evaluator-side distinguishing answers collapse.

The pre-outcome materialization workflow run `31704787171` at branch revision `7e5234c8cab666f13b6712eacc82f8fbd48d8163` succeeded and emitted artifact `9182698390`, digest `sha256:d79a61535d39e76513ca7dc22ae8162f4c6e8afee848178f491729101d9080f9`.

`apparatus-lock.json` freezes the exact corpus roots and manifest hashes. The root algorithm is SHA-256 over the concatenation of sorted `path + NUL + sha256(file_bytes) + LF` records. The locked roots are:

- Plane E: `fee0ca680ebbca21ae25db93a324b15ea0f42fa30874b70686e78050f14748b2`
- Plane K: `c3630c9d6e9a28d6c4549ba26cf2caf14026ebb218dc22b11a0afb138a84ac98`
- R0: `b183d7b7d2a8b27a24e47d32d0b28e55bc427b9829ff3136efaf5dafc47fa03a`
- R1: `77c41df6ea73cd6a5f7d1fae4383246d977c6d4815049844f8f774225fc0828d`
- Meta manifests: `923ef977c67d803eaf47ca599c46ce1f5f45c97bd5b670c841316475480cca80`

Exact meta-file hashes are also frozen for the template, relabeling, query, and collision manifests.

This is **not an O2 result**. No R2 ContextGraph reconstruction, researcher analyzer, acceptance evaluator, or authoritative O2 classification has been produced by this apparatus-lock phase. The lock may not be changed to rescue a later O2 failure.

The scientific boundary remains unchanged: `HISTORICAL_SUBSTRATE_ENABLED = False`, and participants/controllers may not query ContextGraph history.
