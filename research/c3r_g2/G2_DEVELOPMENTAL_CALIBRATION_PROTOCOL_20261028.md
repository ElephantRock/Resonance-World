# G2 developmental variance-calibration stage — FROZEN protocol (2026-10-28 night)

Status: **FROZEN before dispatch** under the owner's GO (2026-10-28
night). NON-INFERENTIAL: variance estimation, response-validity rate
and cost accounting ONLY. The confirmatory N, the full
A/B/C/D/D_MINUS campaign and any Pattern Register promotion are NO-GO.

## Owner-fixed design (verbatim adopted)

| item | value |
|---|---|
| organizations | 12 independent, 4 per environment class |
| arms | C and D only |
| holdout tasks | 8 per organization |
| members | 2 fresh per organization, isolated session per arm |
| send cap | exactly 384 = 12 × 8 × 2 × 2 (O_EXCL ledger) |

## Frozen fixtures (deterministic, seed-locked, before any send)

- Class assignment: organizations 0–3 `unambiguous` (S1-like: 16
  wins / 4 losses for the true plan), 4–7 `noisy_majority` (S2-like:
  13/7), 8–11 `task_conditional` (S3-like: plain 12/6 + special 10/2,
  truth varies by task variant). Corpus: 20 episodes per organization
  for the single-variant classes, 30 for task-conditional
  organizations (18 plain + 12 special); plans, task operands and
  truth bindings derived from the frozen seed domain `g2-devcal-v1`
  (no choice after outcomes).
- Task-conditional organizations get 4 plain + 4 special holdout tasks;
  other classes 8 single-variant tasks.
- Compiler: the frozen qualification compiler (support floor 8, margin
  floor 2, abstention). Abstention → D members execute the pre-declared
  neutral procedure; the `abstention_fallback` FLAG is operational and
  independent of outcome grading (a correct fallback answer counts
  CORRECT with the flag retained; transport/unparseable remain ITT
  failures).
- C members: bounded K=6 deterministic record sample per (member,
  task), context- and variant-visible, both plans named — the probe's
  exact C prompt shape. D members: the probe's exact D prompt shape
  (procedure only, no records).
- Model settings: glm-5.3, coding endpoint, High, 4096 max_tokens,
  temperature 0, 300 s timeout. No retries anywhere.

## Registered cost bounds (before execution)

- **Send cap: 384, permanent per-workspace O_EXCL ledger
  (`g2-devcal-ledger`, slots 0..383).**
- **Token bound: per-request 4096 → theoretical completion ceiling
  1,572,864 tokens; alert threshold at 25% of ceiling.**
- **Financial exposure: the existing Coding-Plan subscription (no
  incremental per-token cash cost on the registered route). If the
  owner substitutes a hard money cap, NOTHING is sent until it is
  registered here.**

## Slot plan (frozen)

Organization o (0..11): block o×32 .. o×32+31. Within a block:
arm C = first 16 cells (member m 0..1 × task t 0..7 → m×8+t), arm D =
last 16 (16 + m×8 + t).

## Declared analysis (in advance; non-inferential)

1. Per organization: mean paired D−C over its 16 (member, task) cells.
2. Per class and pooled: mean, SD across organizations, and a 95%
   chi-square CI on the org-level SD.
3. Validity: per arm/class rates of `completed_parseable` vs
   `empty / length / transport_error`; abstention-flag rate.
4. Cost: sends, latency totals, prompt/completion token totals,
   ceiling usage.
5. **Conservative N inputs (for the freeze decision, not a decision):**
   required N table for the JOINT confirmatory gate (positive +
   significant + estimate ≥ +5pp) under (a) the pooled SD point
   estimate and (b) the UPPER CI SD — the optimistic point estimate is
   never used alone.
6. Sensitivity: class-stratified SDs; if classes are heterogeneous,
   the stratified design must be reflected in the freeze.

## Hard rules

- Developmental organizations, corpora and records are COMPLETELY
  EXCLUDED from any confirmatory sample; fixtures are seed-locked so
  confirmatory draws can be forced disjoint.
- No SESOI change, no mixture change, no compiler/threshold change
  after seeing developmental data; impractical N → the owner
  re-evaluates the investment (no rescue).
- Reserved Probe sends remain untouched. No historical artifact is
  modified. Nothing in this stage promotes any mechanism claim.
