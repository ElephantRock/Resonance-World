# SLRC v2.2 — Identifiability Closure Review (2026-10-29; design only; zero execution)

Status: **the owner's final prospective review of SLRC before any
qualification.** Zero sends; no grid execution; no historical data
modified; C3R-G2 remains closed at 386. This document delivers the
three linked outputs mandated by the owner's decision.

---

## PART 1 — Identifiability proof / counterexample for each primary contrast

### 1.1 The structural tie in clean-change conditions (proven)

Under the v2.1 frozen parameters (4 records/context/gen, 6-record
recency-first budget, majority-of-successes):

After a clean regime change at generation g, the retrieval window for
context c in generation g+1 contains:
- 4 records from gen g (correct, new-regime) — the most recent
- 2 records from gen g−1 or earlier (obsolete, old-regime)

Majority = 4 correct vs 2 obsolete → **UNCURATED already decides
correctly**. SLRC's retirement of the 2 obsolete records changes the
window's composition (6 correct vs 0 obsolete) but NOT the majority
outcome. Therefore:

**Y(SLRC) − Y(UNCURATED) = 0 in `change_early` and `change_late`
(clean noise = 0%) — by construction, not by measurement.**

This is a **structural tie**: the retrieval engine (recency-first,
budget 6) is itself a sufficient implicit curator when the current
generation's admissions fill ≥ 50% + 1 of the budget. SLRC's
detection is causally real but its decision-level effect is invisible
under these parameters.

**Owner's prediction (§5 "RESET may win in change_early/change_late
due to detection lag") is also incorrect for the same reason:**
detection lag in SLRC does NOT delay correct decisions because the
retrieval engine has already moved past the obsolete evidence. RESET
and UNCURATED and SLRC all decide identically in clean-change
conditions.

### 1.2 Where the contrasts ARE identifiable (necessary conditions)

For SLRC's retirement to change a member's decision, the retrieval
window must contain enough obsolete evidence that the majority
flips. This requires:

**Necessary condition for C2_shed identifiability:** the current
generation's admissions must NOT fill ≥ 50% + 1 of the 6-record
budget — i.e., **admissions per context per generation < 4** (the
old evidence must occupy ≥ 3 of 6 window positions and disagree with
the new).

Under the v2.1 parameters (4/gen), this never happens. The contrast
is **structurally unidentified** — not just unmeasured.

**Counterexample demonstrating identifiability at 2/gen:**
- Admissions = 2 records/context/gen. After a change at gen g, gen
  g+1's window = 2 new (correct) + 4 old (obsolete) → majority = OLD
  → UNCURATED decides WRONG. SLRC (if detected) retires the 4 old →
  window = 2 new → majority = NEW → SLRC decides RIGHT.
- **C2_shed > 0 is achievable at 2/gen** — but this is also forced
  (UNCURATED cannot win when old records dominate the window after a
  change). The owner correctly rejects parameter changes that
  substitute one forced design for another.

### 1.3 The general identifiability condition (the real finding)

The decision-level effect of curation depends on the ratio:

```
R = (admissions_per_gen) / (retrieval_budget)
```

- **R ≥ 4/6 ≈ 0.67**: recency-first retrieval is a sufficient
  curator; curation is structurally invisible (C2_shed = 0 always).
- **R < 3/6 = 0.5**: old evidence dominates the window after a
  change; UNCURATED is structurally disadvantaged (C2_shed > 0
  forced, never negative).
- **R ≈ 0.5 (3/gen)**: the boundary — the majority can tip either
  way depending on noise in the current generation's admissions.
  This is the ONLY regime where C2_shed is genuinely two-sided.

**The identifiability boundary exists at R = 0.5 and the v2.1 design
sits at R = 0.67 (structurally tied).** A design at R = 0.5 (3
records/context/gen with 6-record budget) allows both SLRC wins
(clean post-change generations with 3 new + 3 old, majority tips on
noise) and UNCURATED wins (when SLRC's false alarm retires correct
records, the window fills with noise-contaminated new records while
UNCURATED's window still contains the correct old ones).

### 1.4 C1_retain and C3_stability identifiability

**C1_retain (SLRC − RESET in noise-burst):** IDENTIFIED under v2.1
parameters. In a noise burst (25% wrong-plan successes in gens 3–4),
RESET's current-gen window is noise-contaminated (majority may flip),
while SLRC/UNCURATED's window draws on accumulated correct history.
C1 > 0 is achievable and not forced (if the burst is strong enough,
all arms are harmed equally; if SLRC fires a false alarm it loses its
own history and falls to RESET level).

**C3_stability (SLRC ≥ UNCURATED − δ in stable truth):** IDENTIFIED
but must include noisy-stable conditions (owner correction: not just
`stable_clean`). At v2.1 parameters with 4/gen, the window fills
with current-gen records; a false alarm retires correct records but
new correct ones arrive next gen — harm is transient. At lower
admission rates the harm would persist. The contrast is identified
across the stable-noise conditions.

---

## PART 2 — Consistent specification (four issues resolved)

### 2.1 C3_stability scope (corrected)

C3_stability is computed from **all truth-stable conditions**:
`stable_clean`, `stable_burst1`, `stable_burst2+`, `stable_chronic`.
The false-alarm risk materializes in noisy-stable conditions, not in
clean ones. (v2.1 computed it from `stable_clean` only — a
significant under-scoping now corrected.)

### 2.2 Absence of evidence vs zero-sum evidence (distinguished)

| generation type | gen_evidence | counter r | window |
|---|---|---|---|
| no records admitted | undefined (no update) | **unchanged** | **unchanged** (silent generation) |
| records admitted, sum = 0 (equal confirm/contradict) | 0 | **reset to 0** | **updated** (the records enter the window) |

A **silent generation** (no admissions at all — possible in a
degraded-evidence regime) leaves the detector state untouched. A
**zero-sum generation** (equal positive and negative evidence) is
active evidence against a change: it resets the consecutive counter
and enters the window.

**Window aging at W=3:** the window drops generation-level evidence
sums older than the last 3 ACTIVE (non-silent) generations. Silent
generations do not advance the window's time — they are skipped, not
counted as zero-evidence.

### 2.3 Reference initialization (evaluator-truth-free)

Generation 1: all arms start with an empty store. The reference plan
is set by the **first generation's own majority** (among admitted
successes). If the first generation is tied, the reference is set by
a deterministic hash of the condition+seed (declared, evaluator-blind,
and testable for determinism). After generation 1, tie-breaking in
member decisions uses the current reference plan (v2.1 rule,
unchanged). No evaluator truth participates.

### 2.4 Noisy-record generation model (declared)

A noisy record with `graded_success=True` and wrong plan represents a
**real observation in a probabilistic world**: the source agent
executed the wrong plan and the evaluator graded its OUTPUT as
successful because the output happened to coincide with the correct
plan's output on that specific input (a false-positive evaluation
from the evaluator's perspective — the evaluator grades the ANSWER,
not the METHOD). This is the declared observational-noise model; it
is NOT evaluator forgery (the evaluator never injects false records;
real graded episodes happen to be misleading). The model is:
`P(noisy record) = noise_rate` per admitted record; a noisy record
carries the wrong plan with a genuinely graded success.

### 2.5 Right-censored detection/recovery (corrected)

If a regime change occurs at generation 4 (the last stressed
generation) and is detected at generation 5, the recovery-latency
measurement has **0 remaining generations** — the measurement is
**right-censored** and is reported as `"censored"` (not as a failed
or successful recovery). Censored measurements are counted separately
and excluded from recovery-latency summaries. `change_late` chains
where the change is at gen 4 and detection at gen 5 will have
censored recovery.

---

## PART 3 — The binary verdict

### The structural finding

At v2.1 parameters (R = 0.67), the primary shedding contrast
**C2_shed is structurally tied** — the design cannot measure what it
claims to measure. Reducing admissions to force identifiability (R <
0.5) would substitute a forced win for a forced tie (the owner's
correct rejection).

**The only regime where C2_shed is genuinely two-sided is the
boundary: R = 0.5 (3 records/context/gen, 6-record budget).** At this
ratio, the majority in the post-change window depends on noise in the
current generation's admissions — it tips toward new or old evidence
depending on the realization, not the structure. This is a
**parameter change from 4/gen to 3/gen**, declared prospectively
without reference to any prior result (the owner's constraint: "لا
تُستخدم النتائج السابقة لضبط العتبات").

### The verdict

> **IDENTIFIABLE — READY FOR ONE OFFLINE QUALIFICATION** at R = 0.5
> (3 records/context/gen), with all Part-2 corrections applied.

**Justification:** at R = 0.5, each primary contrast has a genuine
two-sided region (proven by the Part-1 analysis):
- C1_retain: identified (noise bursts harm RESET's current-only
  window; false alarms harm SLRC's accumulated window);
- C2_shed: identified at the boundary (majority tips on realization,
  not structure);
- C3_stability: identified across noisy-stable conditions (false
  alarms vs correct retention is a real trade-off).

**However**, the parameter change (4→3 records/gen) is a design
modification that the owner has NOT approved. The v2.1 parameters as
frozen produce a structural tie in C2_shed. Therefore this verdict
is **conditional**: the owner must approve the R = 0.5 parameter or
choose `CLOSE SLRC DESIGN`.

### If the owner does NOT approve the parameter change

The alternative verdict is:
> **CLOSE SLRC DESIGN** at v2.1 parameters (C2_shed structurally
  unidentified; no parameter change without owner authorization).

---

## Frozen v2.2 specification delta (from v2.1)

| parameter | v2.1 | v2.2 (proposed, pending owner) |
|---|---|---|
| records/context/gen | 4 | **3** (R = 0.5) |
| C3_stability scope | stable_clean only | **all stable conditions** |
| silent vs zero-sum gen | conflated | **distinguished** (§2.2) |
| reference init | "current reference" undefined at gen 1 | **gen-1 majority + hash fallback** (§2.3) |
| noisy-record model | implicit | **declared observational-noise model** (§2.4) |
| recovery censorship | not addressed | **right-censored, reported separately** (§2.5) |
| grid conditions | 9 | 9 (same conditions; parameter delta only) |

No SLRC thresholds changed (+2.0 bits, W=3, 0.85/0.15, r≥2, δ=0.05).
No prior result used to set any parameter.
