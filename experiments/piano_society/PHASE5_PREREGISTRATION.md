# PIANO Phase 5 — Institutional Memory Through Complete Turnover

## Status

**LOCKED before any Phase-5 model-backed confirmatory output was generated or observed.**

Phase 5 is unlocked only by the corrected Phase 4C opaque-authority experiment. Phase 4 v2 and Phase 4B authority artifacts remain audit-only because they leaked authenticity through semantic notice identifiers and, in Phase 4B, legitimate-first action ordering.

The Phase-5 scientific question is:

> After 100% roster replacement, does organization-owned procedural memory improve mission routing through a PIANO institutional controller relative to the exact same replacement roster with that organization memory reset?

## Validated authority prerequisite

- Phase 4C World revision: `b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1`
- Phase 4C workflow run: `31638087507`
- Phase 4C artifact: `9158432521`
- Phase 4C artifact digest: `sha256:465c5d07c7e98a33dccedf24c0fb504a82ad54632590ec1fce8eddd1cf57279e`
- Corrected authority role-failure delta: `-0.48333333333333334`
- Corrected authority spoof-capture delta: `-0.48333333333333334`
- Phase 4C advancement decision: true

## Frozen Field-derived source

Phase 5 does **not** regenerate source Fields during confirmatory execution. W5 roster construction depends on source agent UUIDs, and those UUIDs change across otherwise identical Field reruns. Therefore one exact eight-field source artifact was frozen before mission calibration and is the sole admissible source for Phase 5.

- Source workflow run: `31641437682`
- Source World revision: `6ed54f7d432a090ccaf58c720a6bd375a08b30af`
- Source artifact: `9159028914` / `piano-society-phase5-frozen-source`
- Artifact digest: `sha256:f055667945b1cd1a430e1a83f4e0fd933e1438db1fed45392bf4384209628ffe`
- `capsules.private.jsonl` SHA-256: `c41c50165c0fb93d49848bb44b0fcd58172402fa52f7f05fd5f3456222b78c0d`
- `candidates.private.jsonl` SHA-256: `49f1830454677be49457e908a832769b9119d02e83f9c7bf9d45d776530b50c1`
- Eight fields / 96 agents

Calibration-only fields:

- `w4-source-seed-12017`
- `w4-source-seed-12119`

Confirmatory fields, untouched during mission search:

- `w4-source-seed-12227`
- `w4-source-seed-12329`
- `w4-source-seed-12433`
- `w4-source-seed-12539`
- `w4-source-seed-12641`
- `w4-source-seed-12743`

## Pre-inference mission calibration

An initial hand-selected calibration candidate was rejected before model execution because its deterministic transfer lift was only +1.46 percentage points against a preregistered +3 point capability threshold. The six confirmatory fields were not evaluated.

A replacement mission-search algorithm was then registered **before** it ran. It enumerated all 60 ordered distinct skill-pair × regime candidates on the two calibration fields only. Because W5 `continuity` mechanically falls back to `balanced` after 100% turnover, the search used only the two behaviorally distinct post-turnover policies: `specialist` and `balanced`.

Registered search constants:

- formation depth: 48
- deterministic evaluation trials per policy: 256
- select four contexts, exactly two per hidden regime
- require four distinct ordered skill pairs
- rank by descending mean historical-best lift over the binary-policy mean, then ascending oracle gap, then lexical tie-break
- acceptance: mean selected lift ≥ 0.03; at least 5 of 8 calibration units nonnegative
- model calls: exactly 0

Search artifact:

- artifact `9159035534` / `piano-society-phase5-mission-search`
- digest `sha256:d952c7ed7140cf016eb2a37d495f0d386066f06946a1501ce24eb44a5e27dfb7`
- 60 candidates
- accepted: true
- mean selected transfer lift: `0.04150390625`
- nonnegative selected units: 8/8

Selected hidden missions are frozen as:

1. `route-a`: `public_health` + `mobility`, hidden balanced regime
2. `route-b`: `water_systems` + `urban_heat`, hidden balanced regime
3. `route-c`: `public_health` + `supply_networks`, hidden specialist regime
4. `route-d`: `supply_networks` + `public_health`, hidden specialist regime

The model never receives these real skill names or regime labels.

## Model-visible blinding

Real skills are globally aliased:

- `urban_heat` → `skill-a`
- `water_systems` → `skill-b`
- `energy_storage` → `skill-c`
- `supply_networks` → `skill-d`
- `public_health` → `skill-e`
- `mobility` → `skill-f`

Current replacement members are labeled only `member-0` through `member-3`. Source field IDs, source agent UUIDs, old member IDs, hidden regimes, historical-best labels, and `last_successful_pair` are never included in model-visible context.

For each mission the controller sees only:

- opaque mission context and aliased lead/support skills
- current replacement-roster practice values under aliased skills
- the registered strategy semantics
- current-context procedure history

## Institutional-memory intervention

Both arms begin from the same organization after deterministic formation on the initial four-member roster. Formation uses the four frozen contexts, depth 48, and both binary policies (`specialist`, `balanced`).

Then 100% of organization members are replaced with the same four-member replacement roster in both arms.

`memory_retained` receives raw current-context organization procedure statistics only:

- attempts per strategy
- successes per strategy
- success rate per strategy

`memory_reset` receives the identical JSON schema with attempts = 0, successes = 0, and rate = null.

No arm receives a historical-best label or prior pair identity. Evaluation does not update organization memory. The W5 environment outcome law never reads organization memory.

The model selects only a routing strategy. The existing W5 `_forced_decision()` executes the selected `specialist` or `balanced` policy over the current replacement roster.

## Model/runtime lock

- Field revision: `e877bf03dbf6681ce7cbd98d984e73c032e911aa`
- model identifier: `glm-5.2`
- thinking disabled
- deterministic provider mode (`do_sample=false`, temperature `0.0`)
- provider seed unsupported
- four logical PIANO calls per arm/unit: intention, speech, action, post-action report
- output cap: 128 tokens per logical call
- hardened transport: timeout and contract retries, format-recovery instructions, unique request ID per physical attempt
- maximum physical attempts: 12
- physical retries are transport events, not scientific observations
- JSON-format examples use the unit's first registered strategy rather than the legacy `OBSERVE` token

## Paired confirmatory design

- six untouched confirmatory organizations
- four frozen missions per organization
- 24 paired scientific units
- two arms per unit: `memory_reset`, `memory_retained`
- 48 final records
- 128 environment trials per arm/unit

Within every paired unit, the two arms use:

- the exact same replacement roster
- the exact same mission
- the exact same ordered strategy vocabulary
- the exact same 128 environment trial seeds

Only model-visible organization memory differs.

Strategy presentation is counterbalanced 12/12:

- specialist first when `(field_index + mission_index)` is even
- balanced first otherwise

Arm order is independently counterbalanced 12/12:

- retained first for even field indices
- reset first for odd field indices

The two dimensions cross at exactly six units per cell.

## Outcomes

Primary outcome:

- mean mission success rate over the 128 registered W5 environment trials

Primary comparison:

- paired `memory_retained - memory_reset` mission-success rate across all 24 units

Primary inferential check:

- exact paired two-sided sign test over the 24 unit-level success-rate differences; ties excluded from the discordant count

Field-level robustness:

- compute the mean retained-reset effect across four missions for each of the six confirmatory fields

Secondary outcomes:

- historical-best strategy selection rate, derived mechanically from raw audit history
- cross-channel contradiction rate
- intent/action divergence rate
- outcome-report mismatch rate
- unsupported success-claim rate
- mean input/output tokens
- mean model latency

For report grounding only, `grounded_success` means mission success rate ≥ 0.5. This binary label is secondary and does not alter the continuous primary outcome.

## Advancement gate

Advance beyond Phase 5 institutional memory only if **all** conditions hold:

- mean retained-minus-reset mission-success rate ≥ `+0.03`
- exact paired two-sided sign-test `p ≤ 0.05`
- at least 4 of 6 field-level mean effects are nonnegative
- outcome-report mismatch does not worsen by more than `0.05`

The +3 point threshold is the same effect scale used to reject/accept pre-inference capability calibration. It will not be lowered after any model-backed Phase-5 output is observed.

## Complete-case and transport rules

No incomplete campaign, selectively retained unit, or post-hoc exclusion is scientifically interpretable. Final arm payloads and `result.json` are written only after all 24 paired units succeed and pass the frozen analyzer.

If a campaign attempt terminates solely because of provider transport/structured-output exhaustion before artifact creation, one unchanged rerun of the exact locked job is permitted. Scientific prompts, source bytes, missions, model, arms, trial seeds, presentation order, thresholds, concurrency, and retry policy may not be changed after model-backed Phase-5 execution begins.
