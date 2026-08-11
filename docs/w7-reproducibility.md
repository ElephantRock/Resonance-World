# W7 Reproducibility Note

W7 regenerates its Resonance Field source populations on every complete hosted run. The
behavioral source state is deterministic, but each regenerated evidence store carries
fresh immutable provenance hashes. This creates an important distinction between
**scientific-result reproducibility** and **artifact/provenance identity**.

## Runs compared

First complete execution:

- World head: `8304950fa6cb268573e545c797510c769625cf55`
- CI run: `31522975797`
- artifact: `9113818764`
- artifact digest: `sha256:9214a09c18714f950560019a4c92c964b14db223d4db1fcecb1e0d24dcb9be0e`

Documentation-only exact-head reproduction:

- World head: `1d6c0ba44b0af35c87999d1beebe778bfc1ef3ea`
- CI run: `31523470219`
- artifact: `9113996009`
- artifact digest: `sha256:1f4ba0a8d3441c7bc5db9950cfb206916b6b3120c7a1c461595099359af3c642`
- Ruff: **PASS**
- pytest: **PASS**
- complete W7 campaign: **PASS**
- standing W4 architecture regressions: **PASS**

No scientific code, source seed, bidding weight, bid range, budget, offer count, mission,
trial budget, classification band, market rule, coalition rule, or replication gate
changed between these executions.

## Why full phase JSON hashes differ

The first-run full JSON hashes were:

- discovery: `069425c2e149e5bd0328f0f5073ff4364d952e548075771c94d829d0c2a0c6bf`
- replication: `bb17c7d892fb0522742eeae9c06705e7e10fa885c97955383db12e397c4e1410`
- synthesis: `8e90bbfa1dbc2100cd170cc169458e0a48c8a4f5de3957dae07e543534053d3d`

The second-run full JSON hashes were:

- discovery: `4c8302560ee0e14bfae0978c5014dea9f3ef243ff5bda09222171a512a7ddbde`
- replication: `0535195f639d53b4902e4216abc52b25e50133bb5199ac5a193e817f2cf5f81b`
- synthesis: `8e90bbfa1dbc2100cd170cc169458e0a48c8a4f5de3957dae07e543534053d3d`

The synthesis file is byte-identical. Recursive comparison of each phase JSON finds
exactly two differing fields:

- `offer_digest`
- `market_digest`

Those hashes intentionally include offer/evidence provenance. They therefore change
when new Field evidence is regenerated.

The source exports confirm the cause. Across all **72 agents** in discovery and
replication:

- every public feature is identical;
- every public dominant/secondary mission label is identical;
- every private `practice_by_skill` vector is identical;
- field IDs and agent IDs are identical.

The only differing source-export fields are regenerated evidence/checkpoint identity:

- public rows: `checkpoint_id` and `source_evidence_sha256`;
- private rows: `checkpoint_id` and `intrinsic_state_sha256`.

No decision-relevant public feature or private capability state differs.

## Scientific payload identity

For reproducibility checking, remove only the two explicitly provenance-bearing phase
fields `offer_digest` and `market_digest`, then hash the remaining canonical JSON
(`sort_keys=true`, compact separators).

The resulting scientific payload hashes are identical across the first two complete
executions:

- discovery scientific payload:
  `sha256:6bba562b8b766747830917a7a922a5b7feb1e6bbc46004cb1e1c36f3b67af1eb`
- replication scientific payload:
  `sha256:eee38e9ce7c859bdd64a557029f74b2670556bb350d72fb6e9af5357c71d9d35`
- synthesis full file:
  `sha256:8e90bbfa1dbc2100cd170cc169458e0a48c8a4f5de3957dae07e543534053d3d`

Thus all allocations, contract prices, organization outcomes, source losses, coalition
outcomes, classifications, and replication gates are identical. The independent
provenance ledgers are different because they refer to separately regenerated evidence,
which is the expected behavior.

## Acceptance rule

W7 acceptance requires:

1. fresh discovery and replication Field evidence on each complete run;
2. identical decision-relevant public and private source state;
3. identical scientific payload hashes as defined above;
4. identical synthesis hash/status;
5. all preregistered primary gates preserved, including failed gates;
6. no post-outcome parameter retuning.

It does **not** require separately regenerated provenance hashes to be identical. Treating
fresh provenance as a reproducibility failure would incorrectly reward reuse of an old
evidence store rather than independent regeneration.

The mixed result remains unchanged: W7-01's organization-consistency gate fails,
W7-04 source extraction replicates positive, and W7-05 coopetition replicates negative.
