# G2 compiled organizational knowledge vs competent raw-evidence organization — PREREGISTRATION DRAFT (valid for freezing; NOT frozen)

Status: **DRAFT v1, prepared for the owner's freeze decision.** Zero
sends have occurred; nothing is dispatched by this document. Built
under the conditional GO of 2026-10-28 (offline causal qualification
only) and qualified by the offline harness in
`src/resonance_world/c3r_g2_causal_qualification.py` (report:
`evidence_g2_qualification_20261028/qualification_report.json`).

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

## 1. Research question and estimand

> Under a fixed model, matched total work budgets, identical admitted
> evaluator-graded evidence for C and D, and fresh members who never
> participated in development, does executing a compile-ONCE
> organization-owned workflow procedure improve held-out task success
> over competent per-task reinterpretation of the same evidence by the
> same members?

**Primary estimand:** Δ_Organization = Y(D) − Y(C), paired within
organization on that organization's holdout tasks, intention-to-treat.
**Secondary (Holm-corrected family):** D − B (learning component),
D − D_MINUS (procedure-removal attribution). **Context:** D − A
(usefulness baseline), reported descriptive only.

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

**Abstention contract:** when the compiler abstains (support/margin),
D members use the pre-declared neutral procedure; the fallback is
counted in the taxonomy and the outcome stays in the ITT denominator.
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

## 4. Statistical contract (governance fields — proposed values, freeze decides)

- **Experimental unit:** the ORGANIZATION (its own admitted corpus,
  roster of fresh members, and disjoint holdout tasks). Tasks within an
  organization are correlated and never counted as independent units.
- **Design:** paired within organization (D vs C on identical tasks),
  organizations independent across the sample.
- **N (proposed, conventional pending owner decision):** 24
  organizations; minimum analyzable 18 (yield floor from transport
  taxonomy); expected paired discordance to be estimated from a
  bounded noninferential pilot on the live stack before freeze if the
  owner requires it, else fixed at the qualification-derived
  assumption with sensitivity analysis.
- **SESOI / materiality (decision point for the owner):** proposed
  Δ_D−C ≥ +5 percentage points, classified CONVENTIONAL (worksheet
  rule 8: no mission-economics derivation exists yet). The owner may
  set the threshold from mission value before freezing; it may not be
  changed after unblinding.
- **Test:** cluster-aware paired analysis at organization level
  (exact paired permutation on organization-level means as primary;
  bootstrap CI over organizations); alpha 0.05 one-sided for the
  primary, Holm family for the three confirmatory contrasts.
- **Missing/transport policy:** ITT — every transport failure,
  unparseable response and abstention fallback stays as a failure in
  the denominator; analyzable-yield reported per arm.
- **Stopping rule:** fixed N, single look, no interim analyses, no
  threshold adjustment, no rescue redesign.
- **Replication:** a fresh-cohort independent replication is required
  before any promotion beyond discovery-supported (per
  mechanism-governance; this node is posthoc_motivated → proposed).

## 5. Termination and pivot rules (owner-adopted)

- If Δ_D−C fails the frozen gate: **no redesigned procedure, no
  serial rescue.** The program pivots to the H1–H4-supported
  alternative — raw structured history as the persistent knowledge
  channel — and tests ITS institutional properties in a separate
  study.
- A D win that disappears under D_MINUS is reported as a harness
  artifact, not an organization effect.
- Claims boundary: a gated D win supports "compiled organizational
  knowledge has value under the registered resource constraints" — it
  does NOT establish self-learning by the organization (the compiler
  is deterministic and uses externally graded evidence) and does NOT
  establish institutional regeneration across generations (separate
  G3 study, separately gated).

## 6. Live-campaign prerequisites (each its own gate, none authorized now)

1. Freeze this prereg (owner decision, including SESOI and N).
2. Request-class qualification probe on the live stack, bounded and
   campaign-gating (the v2-acquisition pattern): one C-class
   interpretation request and one D-class execution request must
   complete within the registered operating point before any dispatch.
3. Frozen send cap with an O_EXCL ledger; CI-gated dispatch;
   Research-First contract; the two reserved Probe sends untouched.
