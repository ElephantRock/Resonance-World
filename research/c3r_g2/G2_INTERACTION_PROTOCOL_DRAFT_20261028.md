# G2 interaction protocol — DRAFT v2 (unfrozen; analysis & design phase only)

Status: **DRAFT v2 — owner corrections (2026-10-29) adopted; zero
sends; no live GO requested.** The immediate authorized step is ONE
deterministic offline no-forced-sign check.

## 0. v2 corrections (binding)

1. **γ is renamed TAG MASKING RATE** (the probability a record's
   variant tag is masked/uninformative). It is NOT "diagnosticity";
   γ = 0.4 still leaves ~60% of tags visible on average.
2. **γ = 0.4 does not mean information absence, and β = 0 does NOT
   guarantee G = 0** in finite corpora — granularity-splitting can
   weaken per-variant support and overfit noise (possible G < 0).
   These are HYPOTHESES the no-forced-sign check must MEASURE, not
   structural facts to assert.
3. **Grid arithmetic:** the full grid is 5 (α) × 4 (β) × 3 (γ) =
   **60 combinations**, not 20; any subsample must declare its draw
   method and independent replication; one point per combination is
   not a variance estimate. Cross-seed replication is mandatory.
4. **Accounting correction:** in a 960-send design the split is
   **320 C + 640 D-class** (320 D_CTX + 320 D_VAR), not 480/480;
   probe-average token projection ≈ **328K completion tokens for C**
   and ≈ **60K for both D arms combined**; re-estimated at contract
   freeze.

## 1) The independent hypothesis

> The direction and size of compiled-knowledge's organizational value
> are determined by (i) the consistency of graded evidence at the
> level the procedure can represent, and (ii) how much decision
> variance depends on detail the compilation discards — together with
> the compiler's REPRESENTATIONAL GRANULARITY as a designable choice.

This generalizes the calibration's mirror finding instead of
re-demonstrating it. The pre-programmed element of the old design (a
context-only compiler facing variant-dependent truth) becomes one
POINT in a parameter space, not a class label.

## 2) Environment parameter space (continuous, seed-sampled)

Each organization's corpus and tasks are generated from three
continuous parameters (frozen grid/distribution at freeze time):

- **α — evidence consistency** ∈ [0.55, 1.0]: the probability a graded
  record's outcome supports the context-majority plan. Low α = noisy
  evidence (bounded interpretation suffers); high α = clean evidence.
- **β — deviation rate** ∈ [0.0, 0.5]: the fraction of tasks whose
  correct plan deviates from the context-majority plan (task-
  conditional structure). β = 0 recovers the consistent world.
- **γ — tag masking rate** ∈ {0.0, 0.2, 0.4}: the probability the
  variant tag is masked in a record (masked records cannot be used by
  ANY variant-conditioning agent — C's sampling or the D_VAR compiler
  alike; D_CTX pools them regardless). γ = 0.4 still leaves ~60%
  visible.

Parameter values are drawn per organization by frozen seed from a
declared grid — no class labels, no post-hoc selection.

## 3) Arms (the compiler's granularity is now an experimental arm)

| arm | information | mechanism |
|---|---|---|
| C | task + bounded K-record sample (tags visible as present in records) | per-task interpretation (unchanged contract) |
| D_CTX | compiled procedure at CONTEXT granularity | discards variant detail |
| D_VAR | compiled procedure at VARIANT granularity (per-variant support floors; abstains per-variant to the context procedure) | representation-matching compiler |

Estimands (per environment parameters, pooled over the grid):
1. **Δ_CTX(α, β, γ) = D_CTX − C** — when does compile-at-context pay?
2. **Δ_VAR(α, β, γ) = D_VAR − C** — does matching representation to
   structure recover the value?
3. **G = Δ_VAR − Δ_CTX** — the value of representational granularity
   itself (the primary NEW quantity; not pre-programmed in sign:
   at γ high both compilers discard unusable detail and G → 0; at β = 0
   granularity is worthless and G → 0; only in the β-high/γ-low band
   can G be positive — WHERE and HOW LARGE is the question).

## 4) The no-forced-sign pre-condition (offline, before any freeze)

A deterministic idealized model (Bayes-optimal bounded C under the
K-sample; support-floored majority compilers) must demonstrate, across
the (α, β, γ) grid:
- regions where C wins, regions where D_CTX wins, regions where D_VAR
  wins, and non-trivial tie regions (γ high / β 0) — with the SIGN of
  every estimand determined by parameters, not by arm identity;
- otherwise the design ADDS NO KNOWLEDGE beyond the apparatus's forced
  behavior and CLOSES without a single send (owner's closure rule).

## 5) Illustrative scale and cost (to be re-derived at freeze)

- Organizations: ~20 environments (5×4 α×β grid × 3 γ levels sampled),
  1 organization each, 8 tasks, 2 members — arms C, D_CTX, D_VAR:
  20 × 8 × 2 × 3 = **960 sends** (illustrative; ≤ the per-request
  budget already qualified; D-class requests ~3 s/94 tokens, C-class
  ~25 s/1,026 tokens with ~9% exhaustion → projected ≈ 480 C-sends
  ~12,400 s and ~492K tokens; 480 D-sends ~2,900 s and ~45K tokens).
- Statistical plan: powered for the PRIMARY granularity contrast G in
  the pre-declared β-high/γ-low band, with the joint-gate power rule
  (true effect assumed ABOVE threshold; full-gate simulation at
  freeze); stratified SE per the corrected formula; fixed-order
  hierarchical gatekeeping: (1) G in the informative band, (2)
  Δ_CTX slope in β, (3) Δ_VAR vs SESOI.
- All 12 developmental organizations remain excluded; new fixtures
  derive from a fresh seed domain (`g2-interaction-v1`).

## 6) What would close this line (pre-declared)

1. The no-forced-sign check fails (some arm's win is structural) →
   close, no sends.
2. The freeze-time N (from the idealized model's variance + observed
   C-exhaustion yield) is impractical → refer investment viability to
   the owner; no SESOI/mixture rescue.
3. A completed confirmatory run failing its frozen gate → the
   compilation line closes with the raw-history channel (H1–H4) as the
   registered alternative.

## 7) Out of scope

No live dispatch in this document; no reuse of developmental data; no
G3/turnover claims; no Pattern Register promotion; the two reserved
Probe sends remain untouched.
