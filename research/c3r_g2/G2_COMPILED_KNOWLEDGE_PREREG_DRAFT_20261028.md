# G2 compiled organizational knowledge vs competent raw-evidence organization — PREREGISTRATION DRAFT v2 (valid for freezing; NOT frozen)

Status: **DRAFT v2 — owner review 2026-10-28 (evening) corrections
adopted.** Zero scientific sends have occurred; nothing is dispatched
by this document. Offline causal qualification passed
(`src/resonance_world/c3r_g2_causal_qualification.py`,
`evidence_g2_qualification_20261028/qualification_report.json`).
Confirmatory freeze is NO-GO pending the statistical calibration below.

## 0. Corrections adopted from the owner's review (binding on this draft)

1. **Identical admitted evidence is a C↔D requirement only.** A and B
   are structurally different controls (independent baseline; fixed
   procedure) and do not receive the corpus.
2. **No blanket "execution-style requests are stable" claim.** C's
   per-task interpretation requests are heavier than D's direct
   procedure execution; request-class stability is therefore a
   QUALIFICATION obligation per class, not an assumption. Corrected
   stability record: 127/128 evaluable responses across the stepwise
   and semantic-clarity campaigns (one transport failure); 420/420 in
   G1 v9 is send-accounting completeness, not response success.
3. **The C=D degeneracy of the old fixture is a property of that
   fixture's trivially-extractable sufficient statistic.** The
   qualified design below makes C and D process-distinct and proves
   (offline, both directions) that the harness measures divergence
   rather than building it.

## 1. Research question, treatment identity and estimand

> Under a fixed model, an explicitly costed resource regime, identical
> admitted evaluator-graded evidence for C and D, and fresh members who
> never participated in development: what is the organization-level
> effect of **compile-once reusable knowledge** versus **bounded
> repeated raw-evidence interpretation** on held-out task success?

**Treatment identity (v2, explicit):** the contrast is an ARCHITECTURAL
one — compile-once knowledge reused at zero marginal evidence cost,
versus per-task bounded reinterpretation of raw records under a
per-task read budget. It measures the value of compilation and reuse
UNDER THE REGISTERED CONSTRAINTS. It is NOT a claim of pure epistemic
superiority under matched per-decision information: at the single
decision, D's information is the compiled summary and C's is a K-record
sample; total record reads and proposal slots are budgeted and reported
(their accounting is part of the treatment, not a nuisance).

**Primary estimand:** Δ_Organization = Y(D) − Y(C), paired within
organization on that organization's holdout tasks, intention-to-treat,
pooled over the frozen environment mixture (§4.3).
**Secondary (Holm family):** D − B (learning component), D − D_MINUS
(procedure-removal attribution). **Descriptive:** D − A.

## 2. Arms (evidence and mechanism contracts)

| arm | information | mechanism contract | per-task work |
|---|---|---|---|
| A | task only | independent attempts, budget-matched | 1 attempt |
| B | task only | fixed neutral procedure, same roles/step allowance as D | 1 attempt |
| C | task + the SAME admitted corpus as the compiler | each member interprets a bounded sample of raw records per task (context- AND variant-visible tags) | interpretation + 1 attempt |
| D | task + compiled procedure only (no raw records) | compiler reads the corpus ONCE per organization (support floor, margin floor, abstention); members execute | 1 attempt |
| D_MINUS | task only | D with the procedure removed and a matched neutral replacement | 1 attempt |

**Cost accounting (measured, reported, and pre-declared):** D pays
compile cost once (all corpus reads + procedure production); C pays
interpretation reads per member-task. The design guarantees
ΣC_reads ≥ ΣD_compile_reads (verified in the harness across all
scenarios) and equal proposal slots across arms. Compilation cost is
reported separately and attributed to D.

**Abstention contract (v3, corrected):** when the compiler abstains
(support/margin), D members use the pre-declared neutral procedure.
`abstention_fallback` is an OPERATIONAL EVENT flag, distinct from
outcome correctness: if the fallback path yields the correct answer it
is graded CORRECT with the flag retained. Transport failures and
invalid/unparseable outputs remain ITT failures in the denominator.
No post-hoc re-compilation, no threshold change after outcomes.

## 3. Offline causal qualification — what was proven (noninferential)

Six fixture organizations (deterministic, scripted members, no model):

| scenario | result | proves |
|---|---|---|
| S1 unambiguous corpus | D = C = 48/48, paired Δ = 0 | honest tie by evidence clarity — NOT algorithm identity |
| S2 noisy majority (65/35) | D 48 > C < 48, paired Δ > 0 | the harness MEASURES a compilation advantage when evidence structure supports it |
| S3 task-conditional truth | C ≈ 48 > D 24, paired Δ < 0 | the harness MEASURES an interpretation-granularity advantage — the mechanism's granularity is live |
| S4 support below floor | compiler abstains; D = neutral; taxonomy records 48 fallbacks | abstention path exercised |
| S5 injected corrupted procedure | D flips 48 → 0 vs S1 | mechanism liveness (manipulable, not decorative) |
| S6 injected transport failures | 2 transport_error cells per affected arm; 48-cell denominators intact | failure taxonomy preserves ITT |

**Conclusion drawn (and its limit):** the four-arm apparatus can
detect an organization-level difference in BOTH directions and
attributes it to the procedure via D_MINUS; it does not fabricate one.
This qualifies the DESIGN. It says nothing about the live model's
actual behavior — that is what the campaign measures.

## 4. Statistical contract (governance fields — v2, owner decisions 2026-10-28 adopted)

### 4.1 Unit, family and decision values

- **Experimental unit:** the ORGANIZATION (own admitted corpus, fresh
  roster, disjoint holdout). Tasks within an organization are
  correlated and never counted as independent units. The design pairs
  D and C within organization on identical holdout tasks.
- **SESOI = +5 percentage points** — adopted provisionally as a
  CONVENTIONAL decision threshold (not a derived economic-importance
  bound); immutable after confirmatory freeze.
- **α = 0.05 (one-sided primary), FIXED-ORDER HIERARCHICAL
  GATEKEEPING (v3, replaces Holm)** — the causal ordering is
  pre-declared and testing proceeds in the fixed sequence (1) D − C,
  (2) D − D_MINUS, (3) D − B; a claim is tested ONLY if the previous
  claim passed at one-sided α = .05. (Holm ranks realized p-values and
  was therefore corrected per owner review.) Test: exact paired
  permutation on organization-level means with a bootstrap CI over
  organizations.
- **Confirmatory success gate is JOINT (v3):** D − C must be positive
  AND statistically significant AND its pooled point estimate ≥ +5pp.
  Statistical significance alone is insufficient; a significant but
  sub-material estimate does not pass. Power calibration must simulate
  this FULL gate (not significance-only at a true +5pp effect);
  claiming the TRUE effect exceeds +5pp is a stronger claim requiring
  a different test and larger N.
- **Missing/transport policy:** ITT — every transport failure,
  unparseable response and abstention fallback stays as a failure in
  the denominator; analyzable yield reported per arm.
- **Stopping rule:** fixed N, single look, no interim analyses, no
  threshold adjustment, no rescue redesign.
- **Replication:** fresh-cohort independent replication required before
  any promotion beyond discovery_supported (this node is
  posthoc_motivated → proposed under mechanism-governance).

### 4.2 Power calibration at the organization level (why N=24 is exploratory only)

Testing Δ = +5pp at organization level requires the organization-level
SD of paired differences, which the six DETERMINISTIC qualification
scenarios cannot supply. Normal-approximation illustration (one-sided
α=.05, 80% power; N ≈ (z_α+z_β)²·σ²/Δ² with (1.645+0.816)² ≈ 6.18):

| org-level SD of D−C | required N | detectable Δ at N=24 (80%) |
|---|---:|---:|
| 0.05 | 7 | ≈ 3.6 pp |
| 0.10 | 25 | ≈ 5.1 pp |
| 0.15 | 56 | ≈ 7.8 pp |
| 0.20 | 99 | ≈ 10.4 pp |

**N = 24 is retained as an EXPLORATORY planning reference only.** The
confirmatory N is fixed ONLY after an organization-level variance
estimate exists (developmental stage or owner-supplied prior), as
N_confirmatory = max(24, powered N at the frozen Δ and SD), declared
before any confirmatory execution. Minimum analyzable 18 remains
provisional pending yield calibration. No post-hoc inflation, no
post-hoc threshold change.

### 4.3 Frozen environment mixture (prevents S2-only selection)

Organizations are drawn from a PRE-DECLARED mixture mirroring the
qualification taxonomy — one third unambiguous (S1-like), one third
noisy-majority (S2-like), one third task-conditional (S3-like) — with
class parameters (noise ratio, variant prevalence, support sizes)
declared at confirmatory freeze and sampled by frozen seed. Environments
are NEVER selected after observing which class favors D. The primary
analysis pools over the mixture; class-stratified results are
secondary. The request-class probe (§6) and any developmental stage
operate under the same mixture declaration.

## 5. Termination, attribution and pivot rules (owner-adopted; v2 corrected)

- **Removal-attribution rule (corrected per owner review):** a D win
  that DISAPPEARS under D_MINUS (with all else held fixed) SUPPORTS
  attributing the effect to the procedure. A D win that PERSISTS after
  the procedure is removed casts doubt on the attribution — some other
  component would be carrying the effect, and the result is reported
  as such rather than as a procedure effect.
- If Δ_D−C fails the frozen gate: **no redesigned procedure, no
  serial rescue.** The program pivots to the H1–H4-supported
  alternative — raw structured history as the persistent knowledge
  channel — and tests ITS institutional properties in a separate
  study.
- Claims boundary: a gated D win supports "compiled organizational
  knowledge has value under the registered resource constraints" — it
  does NOT establish self-learning by the organization (the compiler
  is deterministic and uses externally graded evidence) and does NOT
  establish institutional regeneration across generations (separate
  G3 study, separately gated).

## 7. Developmental variance-calibration stage (owner GO 2026-10-28 night; confirmatory NO-GO)

One limited NON-INFERENTIAL stage to estimate the organization-level
variance of the primary D−C difference, the response-validity rate and
the real cost, BEFORE any confirmatory N is fixed:

| item | value (owner-fixed) |
|---|---|
| organizations | 12 independent (4 per environment class) |
| arms | C and D only |
| holdout tasks | 8 per organization |
| members | 2 fresh per organization, isolated session per arm |
| send cap | exactly 384 (12 × 8 × 2 × 2), O_EXCL ledger |
| registered cost bounds | send cap 384; per-request max_tokens 4096 (theoretical completion ceiling 1,572,864 tokens); financial exposure = the existing Coding-Plan subscription (no incremental per-token cash cost) — if the owner declares a hard money cap instead, NOTHING is sent until it is registered |
| use | variance estimation, validity rate, cost accounting ONLY |
| inference | non-confirmatory; no mechanism promotion |
| reuse | developmental organizations and records are COMPLETELY EXCLUDED from the confirmatory sample |

**Analysis of the calibration (declared in advance):** report the
org-level mean paired D−C per class and pooled; the SD estimate with
its uncertainty; response-validity rates per arm and class; cost
totals. Conservative variance guidance is mandatory: the confirmatory
N is derived from a CONSERVATIVE (upper) variance bound with class
sensitivity analysis — never from the optimistic point estimate alone.
If the implied N is impractical: NO SESOI reduction, NO mixture
change, NO rescue — the investment's viability is re-evaluated by the
owner.

**Freeze conditions for the confirmatory stage (after calibration):**
N from powered simulation of the JOINT gate (§4.1) under conservative
variance; stratified analysis design; observed validity-yield floor;
documented cost. Mixture parameters, seeds, task-allocation rules and
arm-order balancing are frozen WITHOUT reference to which choices
favored D in the developmental data. Developmental orgs/records are
never reused. The full A/B/C/D/D_MINUS campaign and any Pattern
Register promotion remain NO-GO until the owner separately approves
the frozen confirmatory protocol.

## 6. Request-class qualification probe (EXECUTED 2026-10-28 — 2/2 sends, both classes completed)

Frozen mini-protocol (separate document:
`G2_REQUEST_CLASS_PROBE_PROTOCOL_20261028.md`): one C-class
interpretation request and one D-class procedure-execution request on
the registered model settings, under an INDEPENDENT PERMANENT cap of
exactly two sends (dedicated 2-slot O_EXCL ledger; the two reserved
Probe sends remain untouched). Per send: latency, token usage,
finish reason, parseability and cost are recorded. **Interpretation
rules (owner-fixed):** success of both requests is NOT statistical
proof of stability and does NOT launch anything — it only permits
completing the statistical freeze (§4.2/§4.3); failure of either class
halts the campaign path. The full scientific campaign remains NO-GO
until separately authorized.
