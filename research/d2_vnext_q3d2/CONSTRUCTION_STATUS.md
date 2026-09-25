# D2-vNext-Q3-D2 construction status

Mode: **credential-free construction and marker-absent freeze only**.

Issue: #302.

## Purpose

Q3-D2 is the fresh successor to consumed Q3-D run `36068734507`, which returned `Q3-D-OBSERVABILITY-FAIL` because the semantic observer was attached to the persistent client rather than Hermes' request-scoped client. PR #301 repaired that instrumentation path without authorizing execution.

This revision freezes the prospective Q3-D2 diagnostic envelope around that single observer intervention. It does not execute the diagnostic.

## Frozen diagnostic plan

- namespace: `rw.d2-vnext-q3d2-request-scoped-terminal-boundary-diagnostic.v1`;
- schema: `pairwise_order` only;
- 8 fresh pairs, seed base `16_000_000`, seed step 100;
- deterministic cohort commitment: `fb907354a76cbe843a7f1a59cacffdde2fb7a5d64afe1f7be2585e66ce4b0321`;
- zero overlap with all registered predecessor seed namespaces, including Q3-D;
- 2 provider shards × 4 pairs, provider-local concurrency 1, workflow max parallel 2;
- 220 registered logical calls per shard maximum;
- 36 physical sends per logical call maximum;
- 1,152 physical sends per shard maximum;
- **2,304 physical sends per campaign maximum**;
- no budget borrowing, adaptive N, pair replacement, or workflow rerun.

The 8-pair plan is diagnostic, not inferential. Every Hermes API call must have one request-scoped semantic observation. If at least one strict clean-terminal-empty trigger occurs with complete observability, the evaluator may classify its first structural boundary. No scientific-effect inference is permitted.

## Behavioral invariants

The sole intervention remains the request-scoped semantic observer:

- preserve the Q2/Q3-D provider, model, prompt, response schema, exact parser, retry rule, iteration/token limits, tools, memory/session, fallback, and transport guard;
- call Hermes' original request-client factory exactly once with unchanged arguments;
- call each returned client's original `chat.completions.create` exactly once with unchanged arguments;
- return the exact response object unchanged or re-raise the same exception;
- retain only structural metadata, bounded enums/counts/lengths, token counts when returned, SHA-256 commitments, and transport status/error type;
- retain no raw prompt, provider body, assistant content, retry content, or terminal content;
- fail closed on semantic/API-call count mismatch or transport-association mismatch.

## Marker-gated future apparatus

The future execution marker path is `research/d2_vnext_q3d2/RUN_D2_VNEXT_Q3D2` and **must remain absent in the frozen candidate**.

The future workflow `.github/workflows/d2-vnext-q3d2-diagnostic.yml` is marker-gated, requires run attempt 1, checks the marker's exact candidate parent SHA, issue number, authorization string, and 2,304-send ceiling, and rejects a candidate that already contains the marker. No provider job can start before that authorization-integrity job passes.

The exact marker-absent candidate SHA is determined only after this construction revision is merged and the dedicated qualification branch is pointed exactly at that merged SHA.

## Authority boundary

Provider/model execution is **NOT AUTHORIZED**. No Q3-D2 execution marker exists in this revision.

Q3-D is consumed and must not be rerun. Q2-A/Q2-B are not authorized. Scientific-effect gates, Acceptance, registry promotion, D2e, deployment/publication, credential/permission changes, and Historical Substrate actions remain unauthorized.

Any live Q3-D2 run requires separate explicit human authorization naming the exact frozen marker-absent candidate SHA and an explicit ceiling of **2,304 physical provider sends**.
