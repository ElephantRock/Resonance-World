# C3R G1 multi-schema acquisition pilot v2 — offline construction

**Status: unfrozen, synthetic, credential-free fixture; NO G1/G2 scientific inference.**

The v1 G1 pilot offered multiple opaque contexts of one arithmetic task
schema. The v2 pilot adds **two genuinely different executable task
algebras**. The intent is to validate that an agent's externally retained
feedback can guide a new session on two distinct families, not to claim
generalization to unseen task families.

## Run

```bash
python -m resonance_world.c3r_g1_multischema
pytest -q tests/test_c3r_g1_multischema.py
```

The default command injects constant-action **offline** ports, performs
**zero Z.AI requests**, reads no credentials, and produces deterministic
canonical JSON labeled `offline_fixture_no_model_learning_claim`.
The generic port-injection API is **untrusted** and does not attest whether
a third-party caller performs network operations. Its report labels such
runs `unverified_injected_ports_no_inference`; it never certifies a real
physical-send count.

## Mechanically distinct families

| Family | Choice A | Choice B |
| --- | --- | --- |
| Arithmetic | `(value + offset) * factor` | `value * factor + offset` |
| Text | `text.replace('ab', 'z').upper()` | `text.upper().replace('ab', 'z')` |

Public operands ensure different results for A and B in both families.
For text, e.g. `abroadab` yields `ZROADZ` (A) versus `ABROADAB`
(B). Unlike two arithmetic contexts, text manipulation has different
inputs, transformations and output type.

Each unit has **one opaque context per family**, with an independently
chosen fixed target A or B. The public `SchemaTask` contains neither
this target nor its correct output. `LocalFixtureEvaluator` receives
the private rule separately from the public cohort. Its private seed
can be changed without altering the cohort digest, and it rejects tasks
that are not members of the locked public cohort.

**Epistemic limit:** this separation is within one Python interpreter.
The fixture target mapping remains algorithmically recoverable by a
developer knowing the local private seed. The public cohort digest does
not cryptographically bind target truth and is **not** independent
evaluator attestation. Real G1 testing needs a separately controlled
evaluator service with a prospective, private signed target commitment.

## Prescribed budget (logical calls, not live expenditure)

| Item | Offline v2 plan |
| --- | ---: |
| Separate learner units | 8 |
| Distinct task schemas per unit | 2 |
| Development tasks per unit/family | 6 |
| Qualification tasks per unit/family | 8 |
| Training logical actions | 96 |
| Matched three-arm qualification triplets | 128 |
| Qualification logical actions | 384 |
| **Total local logical actions** | **480** |
| **Provider requests in default CLI** | **0** |

The fixed cap on `V2Design.logical_calls` is 480. It does **not**
reserve or cap real HTTP calls for injected ports. A future provider
pilot requires dedicated transport-enforced pre-send reservations,
network/concurrency caps, retry prohibition, finite monetary ceilings
and a separately authorized operating protocol.

## Arms, history and heldouts

- **Learned:** makes development decisions and receives Boolean grades
  only *after* submitting an exact A/B answer. The action and grade
  enter an explicit per-context source feedback log. A newly created
  **qualification port** receives only that accepted development log;
  the source-development port is not reused.
- **Fresh:** distinct newly created port with no source history.
- **Placebo:** receives the same **number of accepted historical records**
  and task/context identities, but both its plan choices and feedback
  labels are constructed deterministically from a public fixture-specific
  hash. They are independent of learned policy choices and real graded
  outcomes. This avoids a v1 confound in which a learned plan trajectory
  could reveal the target through the placebo trace.

Three-arm order rotates within each identical public heldout task.
No qualification grades are ever delivered to subsequent queries.
All four port objects per learner (development plus three qualification
ports) must be unique, and objects cannot be reused across units.

**Limits of the placebo:** it matches visible history length, task IDs
and context labels, **not** exact prompt token lengths, plan frequencies,
history plausibility or provider-side compute. A model may react to
inconsistent fake feedback; an independent control-validation study and
matched token/latency budgets remain required.

## Output quality, estimand and incomplete data

Every prescribed logical attempt is included even if the port raises
an exception, returns the wrong model ID or produces malformed text.
Such attempts are ITT failures, not silently dropped cases.

Primary *descriptive* contrasts are calculated **per independent
learner unit**:
- ITT learned success minus fresh success, with all heldout tasks in
  the denominator.
- ITT learned success minus placebo success, with the same denominator.

The final descriptive number is the equally weighted mean of the unit
contrasts. The report also includes arm-level and **family-level**
prescribed/accepted/ITT-success counts, full-triplet yield, per-attempt
status, and a self-generated attempt-ledger SHA256. Both families must
be inspected separately; pooling can conceal a failure in one family.

Engineering-only target gates:
- >=95% heldout answer parseability across the three arms;
- >=90% complete triple-arm heldout tasks;
- all source development actions parseable.

A synthetic pass does **not** authorize a live campaign and does not
establish any cognitive G1 acquisition. The `scientific_acceptance`
field is permanently false in v2.

## Regression safeguards

Tests verify (1) genuinely different executable semantics, (2) correct
public/private split including an opposite private answer key on an
identical cohort, (3) distinct dev/holdout IDs and payloads, (4)
zero treatment effect under three identical action policies,
(5) a feedback-responsive synthetic positive control, (6) placebo
independence from source actions/outcomes, (7) no qualification feedback
leak, (8) freshly constructed ports, and (9) all invalid/missing
completions counted in the full prescribed denominator.

## Scientific blockers before a *prospective* real-model G1 study

1. Independent evaluator-owned randomization, private answer-key lock
   and grade attestation; enforce evaluator separation across processes.
2. Preflight on **different calibration inputs** to achieve stable
   answer and triplet yield for GLM-5.3 with one frozen compute budget.
3. Model/session parity; real port identity and isolation; provider-side
   physical-send and billing reconciliation. Same token and thinking
   budgets across all qualification arms.
4. Quantitative sham plausibility/token matching and sensitivity to
   source-history length. Test memory ablation and true-session reset
   while avoiding cached-provider contamination.
5. More than two task families and a genuinely **unseen-family**
   transfer arm if the scientific hypothesis includes out-of-schema
   generalization. Two trained families alone cannot prove such
   transfer.
6. Independent learner-unit replication, prospective sample-size and
   power calculations, pre-registered effect-size threshold and
   cluster-aware inference, blind heldouts and attrition policy.

Do not add this fixture's results to frozen W/H/D evidence or a
mechanism/pattern registry. It is a scientific apparatus construction
under Draft PR #310, not proof of Models → Agents, G2, G3 or G4.
