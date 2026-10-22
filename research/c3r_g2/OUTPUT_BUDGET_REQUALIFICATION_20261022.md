# C3R G1 — output-budget technical requalification, 2026-10-22

**Status:** one-shot launch commit created; result not yet reconciled.
**Scientific classification:** `engineering_smoke_only`, not G1/G2 evidence.

## Why this follow-up exists

The 2026-10-21 artifact recorded 8/8 HTTP 200, 8/8 *empty final answer*
digests, and every response consumed the previous `max_tokens=16`. No
action was parseable, no source acquisition episode was admitted, and no
qualification pair was analyzable. See
`ONE_SHOT_ARTIFACT_ANALYSIS_20261022.md` for the unchanged source record.

Z.AI's official GLM-5.3 documentation specifies mandatory thinking
(`thinking.type: enabled`), support for `reasoning_effort: low`, and the
OpenAI-compatible Coding Plan base URL
`https://api.z.ai/api/coding/paas/v4`. These are transport facts,
not evidence that a model will learn. Provider docs:
`https://docs.z.ai/guides/llm/glm-5.3`.

## Technical change and fixed scope

- Model: `glm-5.3`, explicit `coding` route and pre-existing repository
  secret `secrets.ZAI_API_KEY`; no new secret.
- Source requests: 4 development episodes plus 2 learned and 2 fresh
  qualification attempts; eight logical tasks total, no semantic experiment
  redesign.
- Reasoning: `thinking: {type: enabled}`,
  `reasoning_effort: low` (GLM-5.3 mandatory thinking).
- Output: `max_tokens=512`, 30-second per-request deadline. At most
  8 physical sends * 512 output tokens = 4096 configured output tokens;
  usage fees and quotas must be reconciled separately.
- Hard stop: one HTTP failure/timeout/malformed response already opens
  the circuit. **NEW:** an HTTP-200 response with an empty final answer
  *and* `finish_reason=length` or complete token exhaustion also
  opens the circuit; subsequent logical tasks remain recorded with
  `ProviderCircuitOpen`, without further physical calls.
- Information captured: `finish_reason` restricted to bounded
  classifications, output SHA256, reasoning-present flag and numeric
  reasoning tokens if reported. Never retain reasoning or raw final text.
- Integrity audit: an early empty-answer circuit stop is accepted only
  if the final physical ledger entry has HTTP 200 and a matching
  `EmptyFinalOutputLengthCap` error, an empty-output SHA256 and
  finish/usage evidence. The verdict is always **unattested**, never
  model-acquisition evidence.

## Isolated one-shot execution

A new branch `experiment/c3r-g1-budget-smoke-20261022` was based on
reviewed PR #310 head `79787efaac17cfd6001570d86475d6ca3b6c95ec`.
The one-shot trigger commit is
`5fccb899d4601cceebfd35bef36f83b2b2d98f12`.

Temporary workflow:
`.github/workflows/c3r-g1-output-budget-once-20261022.yml`.
It has an exact branch filter, an exact commit-message equality gate,
read-only contents permission, a bounded write permission to post
sanitized **technical counters only** in PR #310's discussion,
and a constrained `c3r-provider-qualification` environment. It has
no pull-request/main trigger.

Planned artifact:
`c3r-g1-512-token-one-shot-20261022`, containing bounded JSON report
and offline audit if generated. One summary comment, if the runner
possesses permission, links the GitHub run ID and contains only
self-reported counts, not raw output or secrets.

The workflow file should be retired after the launch event and the
run's status is read. Additional pushes with different messages
cannot satisfy the job's exact-message gate.

## Decision table (not outcome claims)

| Observed outcome | Next gate |
| --- | --- |
| GitHub run absent/no artifact | Mark unobserved; do not invent send counts |
| Missing credential/failed offline tests | Zero provider sends if failure precedes dispatch |
| HTTP/non-200 or timeout | Circuit opens after one failed physical send |
| HTTP 200 but empty final response at token cap | Circuit opens, logical denominator stays 8 |
| One parseable action or more | Technical transport worked; inspect quality/yield only |
| Multiple parseable actions and nonzero paired yield | Eligible to design a **separate prospective** G1 study, not evidence of G2 |

Independent transport/provider billing attestation, prospective statistical
design, replicates and org-level causal comparison remain required.
No W/H/D records, scientific registry, World outcome laws, authority ledger
or default historical memory are changed.

## Observed one-shot outcome — authenticated GitHub Actions read

The temporary run **did execute**. The technical smoke and structural audit
both completed successfully; the overall GitHub job conclusion was **failure**
because the separate PR-comment step received `HTTP 403 Resource not
accessible by integration`. This is a GitHub Actions token/permissions
failure, not a provider transport or parser failure.

- GitHub Actions run: `https://github.com/ElephantRock/Resonance-World/actions/runs/39731691610`
- Trigger commit: `5fccb899d4601cceebfd35bef36f83b2b2d98f12`
- Authenticated run's artifact ID: `12405735173`, named
  `c3r-g1-512-token-one-shot-20261022`.
- A separate **read-only** PR-triggered GitHub Actions reconciliation run
  `https://github.com/ElephantRock/Resonance-World/actions/runs/39733094082`
  authenticated to GitHub, downloaded the ZIP, and executed the offline
  source cohort/ledger audit. Result:
  **`structurally_consistent_unattested`**, no structural issues.
- Recovered self-reported physical sends: **6**, all six ledger entries report
  HTTP 200. Two remaining logical attempts were denied by the local circuit.
- Development: **4 scheduled / 4 accepted / 3 succeeded**.
- Learned qualification: **2 scheduled / 1 accepted / 1 succeeded**.
- Fresh qualification: **2 scheduled / 0 accepted / 0 succeeded**,
  including one empty final response at the enlarged generation cap.
- Total: **8 scheduled / 6 sent / 5 accepted**, with 4 correct accepted
  actions. **0 of 2 pairs analyzable**.
- Local reason for early stop: `EmptyFinalOutputLengthCap`, representing an
  HTTP 200 final reply with empty content and documented token/finish-cap
  exhaustion. The circuit correctly prevented the last two sends.
- The original run's `Verify engineering guards`,
  `Authorized coding task technical probe`, `Independent structural audit`
  and `Persist bounded report and audit` steps all concluded **success**.
  Only the informational PR-comment step failed (`HTTP 403`).
- The temporary trigger YAML was removed from its isolated branch, and the
  PR-side read-only reconciliation YAML is also retired after reporting.
  No further provider sends occurred during reconciliation.

### Bounded interpretation

The corrected 512-token setting produced **five parseable actions** where
the original 16-token run produced none. This demonstrates improvement
in technical output yield for this very small construction task; it does
**not** establish the attribution of the improvement without a controlled
model-condition comparison.

One qualification pair requires accepted actions from **both** the trained
and fresh model. There were **zero** such pairs, so no trained-vs-fresh
effect is estimable here. Successful answers during training (3/4) and a
single trained-only qualification success (1/2 prescribed) cannot be
promoted into G1 evidence. No organizational G2 treatment ran.

For future research: retain the complete prescribed denominator, lock
output budgets in advance, include usable-pair/yield criteria, and avoid
treating GitHub comment permission failures as provider failures.
Provider billing receipts and evaluator attestation remain outside this
artifact; scientific acceptance stays **false**.
