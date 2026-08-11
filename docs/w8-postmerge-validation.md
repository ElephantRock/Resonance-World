# W8 Post-Merge Validation — Accepted

Status: **COMPLETE — ACCEPTED POST-MERGE**

The W8 scientific state was merged to `main` at
`21705e36b7c8d90bce642c5d277cfb2274a58d39`. PR #74 was reset to that merged state and
added only the documentation trigger used to request an independent post-merge
regeneration. No W8 scientific code, configuration, source seed, Field pin, threshold,
mission, regulatory rule, budget law, replacement rule, coalition rule, or synthesis
criterion changed for validation.

## Authoritative post-merge regeneration

- validation PR: #74
- validation head: `32ea6a07115108508576cdbcc599e26a2c6312e2`
- CI run: `31538518421`
- ordinary Ruff / pytest job: **PASS**
- complete W8 campaign job: **PASS**
- artifact: `9119826813`
- artifact digest:
  `sha256:ba9dc117c2954cbe6f2cbd25677120264f5da8ddfa1d50b68b20ccc0a6aaa5ee`

The campaign regenerated the 5-Field / 60-agent discovery cohort, native successor
assays, five entirely fresh W8-07 replication Fields / 60 agents, W8-01 through W8-06,
and the corrected synthesis.

Compared with corrected-label reproduction artifact `9119434961`, the discovery and
W8-07 scientific objects are exactly equal after recursively removing only regenerated
`evidence_refs` provenance fields. `w8-synthesis.json` is byte-identical with SHA-256:

`734b007cfbd183ea649f1df6ffe0f8593ba61c00a711c9883edc9c15d84b8c52`

The accepted synthesis remains:

**`replicated_non_sustainable_regulatory_regime`**

## Closeout

PR #74 was merged as `8d8d2a61fd1e592bef4e66010e217a4cf47fa5db`. The temporary
branch-specific W8 campaign CI hook was then removed from `main` in
`936f81a85a031d4001e8399fc89e7cedea3756db`, with standing CI and W4 regression checks
passing. Issue #71 is closed as completed.

W8 is therefore closed with its preregistered negative/mixed result preserved. No failed
scientific gate was retuned or replaced during post-merge acceptance.
