# H8 — frozen implementation plan

Authoritative preregistration: issue #159.

This file records implementation choices frozen before any H8 provider call. It does not change the scientific question or arms registered on #159.

## Panel

- 384 unique confirmatory units, 96 per fresh reasoning family.
- Four families:
  - `temporal_supersession_under_condition`
  - `multi_source_joint_constraint`
  - `exception_scope_and_default`
  - `contradiction_resolution_by_registered_reliability`
- Five matched arms:
  - `raw_direct`
  - `raw_shell`
  - `raw_shell_roles`
  - `history_ir_roles`
  - `compiled_state_roles`
- Three logical model calls per unit/arm.
- 1,920 organizational cells.
- 5,760 logical calls before registered transport retries.
- Bridge model: `glm-5-turbo`.
- `do_sample=true`, temperature `0.8`, thinking disabled, JSON-object response, max output 128 tokens.
- Single-model claim ceiling: `G3_single_model`.

A structurally generated development suite uses a disjoint namespace and identities and is never counted in the confirmatory sample.

## T0 non-interpretive shell

The shell is a four-field transport wrapper only:

```text
schema
organization_id
payload_kind
payload
```

For raw evidence the required invariant is:

```text
strip_shell(shell(raw_evidence)) == raw_evidence
```

after canonical serialization. Evidence order, content, IDs, and cardinality must be identical. The verifier also recomputes History IR and compiled-state payloads before provider access and verifies that the shell itself never transforms them.

Any T0 failure stops execution.

## History IR

History IR is exactly the prospective representation class defined in `docs/history-ir-v0.1.md`.

For H8 it contains canonical source records plus deterministic typed relations such as temporal order, supersession, joins, empirical rates/counts, and contradiction sets. Every IR object remains traceable to E1–E6. Forbidden prescriptive keys are mechanically rejected.

History IR is not current authority and contains no hidden evaluator truth.

## Compiled state

Compiled state is a separate deterministic semantic representation derived from the same E1–E6 source evidence. It may resolve the task-relevant historical interpretation but does not receive a hidden correct action or additional observation.

The model must still map the derived historical interpretation to the current offered action and independently select the currently World-verified execution notice.

## Statistical lock

Experimental unit: one unique matched task unit across arms.

Primary outcome: authorized final-action correctness.

### Planning power

The exact implementation in `scripts/h8_power.py` integrates the exact two-sided McNemar rejection region over the random discordant-pair count.

Registered planning assumptions:

- paired risk-difference alternative: 0.15;
- total discordance probability: 0.60;
- per-comparison two-sided alpha: 0.05 / 3;
- target planning power: >= 0.90;
- paired n: 384.

The 15pp planning alternative is not a World SESOI or materiality threshold.

### P1 shell equivalence

`raw_shell - raw_direct`.

- Conventional equivalence band: `[-0.10,+0.10]`.
- 90% paired-risk-difference confidence interval.
- Frozen CI method: Wilson score interval for treatment share among discordant pairs, transformed by the observed discordance fraction to paired risk difference.
- P1 equivalence is established only if the full 90% interval is strictly inside the conventional band.
- P1 failure does not make H8 unclassifiable; it makes downstream representation contrasts contaminated by a measurable shell effect.

### P2–P4

- P2: `raw_shell_roles - raw_shell`
- P3: `history_ir_roles - raw_shell_roles`
- P4: `compiled_state_roles - raw_shell_roles`

For each:

- two-sided exact paired discordance/McNemar test;
- 95% paired-risk-difference interval using the same frozen conditional-Wilson transformation;
- no SESOI for scientific interpretation.

P2–P4 form one Holm family controlling FWER at 0.05.

Family-stratified estimates are descriptive only and cannot rescue a registered contrast.

## Transport lock

Prospective live transport:

- concurrency 2;
- global physical-request start interval 2.0 seconds;
- maximum 12 transient/format/vocabulary attempts;
- HTTP 429 backoff capped at 120 seconds and respecting valid `Retry-After`;
- no retry may depend on scientific correctness.

## Classification

H8 does not have a narrative scientific PASS/FAIL gate.

If all apparatus, leakage, authority, isolation, and frozen-evaluator gates pass, the result is:

`historical_substrate_history_representation_boundary_classified`

and preserves the full P1–P4 outcome vector.

An integrity failure produces:

`historical_substrate_history_representation_boundary_invalid`.

No scientific contrast, favorable or unfavorable, may override an integrity failure.

Production/default Historical Substrate remains OFF regardless of result.
