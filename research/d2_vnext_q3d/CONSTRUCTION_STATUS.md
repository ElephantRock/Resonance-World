# D2-vNext-Q3-D construction status

**Origin:** #296  
**Implementation/freeze:** #298  
**Mode:** credential-free construction and validation only  
**Provider/model execution:** **NOT AUTHORIZED**

Q3-D is a diagnostic successor to the consumed Q2-A stream. Its purpose is to localize the first structural disappearance or rejection of terminal assistant content across the provider → Hermes → terminal-adapter → exact-parser chain while preserving Q2 behavior.

## Frozen diagnostic sample and envelope

- fresh namespace: `rw.d2-vnext-q3d-terminal-boundary-diagnostic.v1`;
- schema: `pairwise_order` only;
- fresh pairs: **16**;
- shards: **4 × 4 pairs**;
- deterministic cohort commitment: `e01208b5ae2e1665ff7990d235d3485e055cb71fb53ea31da8455f41f24b4cc0`;
- maximum physical sends per logical call: **36**;
- maximum physical sends per shard: **1,152**;
- maximum future campaign physical sends: **4,608**;
- budget borrowing, adaptive N, and failed-pair replacement are prohibited.

This is a localization cohort, not a scientific-effect sample.

## Behavioral and content invariants

- no Q2-A rerun, rescue, replenishment, or marker cycling;
- no Q2-B execution;
- no new rescue mechanism, parser relaxation, prompt/task change, fallback, third invocation, tools, memory, session, or unregistered HTTP path;
- the Q2 provider/model/product/Hermes/parser/retry settings remain frozen;
- provider semantic-completion instrumentation returns the exact original provider response object and adds no provider call;
- no raw prompt, provider response, assistant content, or retry content may be retained;
- structural enums, counts, lengths, token accounting when returned, and SHA-256 content commitments only.

## Authority boundary

The future marker-gated workflow is `.github/workflows/d2-vnext-q3d-diagnostic.yml`, but **the execution marker is absent**. The workflow cannot enter provider jobs without a sole-child authorization commit satisfying its exact-candidate integrity checks.

Future Q3-D live execution requires separate explicit human authorization naming the final frozen marker-absent candidate SHA and the hard **4,608 physical-send** campaign ceiling. Construction or merge does not grant that authority.

No scientific-effect, Acceptance, Mechanism Registry, D2e, deployment/publication, credential/permission, or Historical Substrate action is authorized.

The machine-readable contract is `D2_VNEXT_Q3D_CONTRACT.json`; the structural schema is `D2_VNEXT_Q3D_OBSERVABILITY_SCHEMA.json`; the committed fresh cohort and shard envelope are `D2_VNEXT_Q3D_COHORT_LOCK.json` and `D2_VNEXT_Q3D_SHARD_MAP.json`.
