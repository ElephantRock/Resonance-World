# C3R G1 — opt-in eight-send technical qualification runbook

**Status:** provider adapter constructed / offline verified (subject to CI) / no live run recorded.
**Authority:** user authorized continued implementation and provider qualification on 2026-10-21. This does not grant scientific mechanism acceptance, D2 campaign reruns, unlimited spending, or unrestricted access to credentials.

## Technical distinction

- `src/resonance_world/c3r_g1_zai_transport.py` implements an **explicitly enabled**, single-send-per-call Z.AI **standard API** connector against an explicit allowlist of two routes. The **coding task** uses `https://api.z.ai/api/coding/paas/v4/chat/completions`; the default-off **standard** route remains `https://api.z.ai/api/paas/v4/chat/completions`. The CLI does not accept arbitrary URLs.
- It does **not** import Hermes, reuse D2 Q2/Q3 credentials/authority, or start network traffic on import.
- It reserves one physical-send slot in the shared in-process ledger **before** each request. An HTTP rejection, network exception, timeout, or malformed provider response **opens a terminal circuit** and prevents subsequent sends; the other prescribed logical tasks remain in the denominator as failed attempts. The failed physical send retains its reservation. Invalid A/B action text counts as an invalid-format outcome but need not stop the run. There is no retry, failover, redirect or tool access.
- At most **8** physical POSTs may be attempted in a single smoke process. This is a technical expenditure cap, not a promise of fixed monetary costs; model/provider prices and billable token accounting are outside its control.
- The corrected GLM-5.3 technical probe allows a **30-second timeout** and a maximum of **512 generated tokens per request**. Eight sends therefore have a combined upper ceiling of 4096 generated tokens, not a fixed billable charge. A truncation with an **empty final answer** closes the provider circuit to stop repeating the previous reasoning-only failure.
- The existing GitHub repository secret is **`ZAI_API_KEY`**. The manually dispatched workflow passes its value into the CLI process as `C3R_ZAI_API_KEY` (an **environment variable alias, not a second GitHub secret**). Neither raw provider text nor the API key is preserved in reports; the adapter also redacts the key from its representation.
- The implementation uses Python's standard-library HTTP client with a pinned HTTPS endpoint and redirects disabled; it does not depend on, or modify, frozen Hermes SDK runtime behavior.
- A test double implementing the port is **not** a live model result, and the port's in-process ledger is **not** an external provider billing reconciliation.

## Offline preflight (default, does NOT access the network)

```bash
python scripts/run_c3r_g1_live_smoke.py
```

Outputs `offline_preflight_no_sends`, prospective cohort digest and an exact eight-send ceiling. It requires no secrets and does not authorize any provider request.

## Opt-in technical qualification

Only in an explicitly controlled execution environment, using the existing `ZAI_API_KEY` and the previously used **Coding Plan** endpoint for a narrowly scoped *software implementation selection* task, with an explicit model and observed quota/cost review:

```bash
# For local execution, map the existing ZAI_API_KEY privately to C3R_ZAI_API_KEY.
# GitHub Actions performs this aliasing automatically.
python scripts/run_c3r_g1_live_smoke.py --live --model glm-5.3 --route coding --max-sends 8
```

The operator should verify service access and intended billing plan before executing. The exact eight logical requests are: **4 source development, 2 learned qualification, 2 fresh qualification** under a single shared ledger. Once a physical request is attempted, its budget remains spent regardless of transport or parse outcome.

The example uses one opaque context and the same arithmetic ordering task schema, with the target ordering fixed at B. Its purpose is to test network/provider semantics, feedback separation, and analyzable yield, **not** to discover an effect. A fixed target may favor or disfavor an initial model policy; qualification is not powered or blinded from the operator.

The report always carries `technical_smoke_not_scientific_evidence`, the cohort digest, per-stage attempted/accepted/failure totals, per-call output digests, bounded finish/usage diagnostic metadata, and transport reservation outcomes. Never store or expose credential values or raw provider outputs when sharing this report.

## Failure handling and stop rules

- Missing `--live`, model identifier or CLI environment variable `C3R_ZAI_API_KEY`: no network. The manual GitHub workflow injects it from the existing `secrets.ZAI_API_KEY`.
- Unexpected credential/endpoint/model availability: stop and report; do not silently switch provider routes or model identities. The coding task uses an explicitly selected Coding Plan endpoint already present in prior D2 code, not the general-balance endpoint.
- Eight reservations exhausted: fail closed; no ninth request, even if previous calls failed.
- HTTP 3xx/4xx/5xx, timeout, malformed response: no raw error body, no retries; attempt remains accounted.
- Invalid model action: no answer repair or hidden grader hint; it remains in the prescribed denominator. If the model consumes its generation limit while returning **empty final content**, the run halts after that send. Other invalid-format answers can be recorded without necessarily halting.
- Provider authorization is **not** permission to interpret this smoke as confirmatory G1 acquisition or causal G2 organizational capability.
- Any later campaign needs an independently precommitted sample and evaluator, service-side or gateway-enforced attribution for physical sends, cost cap and observed yield, matched pre/post model sessions, inferential organization units, prospective power and pre-registered G1/G2 criteria.

## Where this runbook stops

The linked GitHub tool surface can write code and read CI results, but has no exposed workflow-dispatch action to start an authenticated experiment. The workflow must be made available from the default branch before GitHub Actions can list it for manual dispatch; this draft PR remains unmerged. The repository's CI intentionally runs only offline tests. A separate authorized operator environment with a private standard-API credential is required to execute this CLI. No provider response should be claimed until an actual bounded run log and accepted report exist.

References: Z.AI's official API documentation for standard `chat/completions` at `https://docs.z.ai/`, plus existing C3R `MODEL_PREFLIGHT.md` and `DESIGN_WORKSHEET.md`.

## Reusing the existing repository secret

The repository already has a secret named `ZAI_API_KEY`. **Do not create or rename it.** The workflow maps `secrets.ZAI_API_KEY` to the existing CLI variable `C3R_ZAI_API_KEY`. Existing D2 code pins the Coding Plan route and model `glm-5.3`; C3R uses that specific route only for this limited programming-task smoke, not to draw a conclusion about prepaid general API balances. The credential's successful past use is evidence of past provider access, not evidence that this particular technical run has completed. Existing D2 experiments and their secret handling are unchanged. For governance, configure required reviewers on the `c3r-provider-qualification` environment before the first manual run; workflow names and environment labels alone do not ensure approvals.

## Authorized one-shot CI execution

The user explicitly authorized the limited live attempt. Because the connected GitHub tool does not expose manual workflow dispatch, an isolated one-shot push-only workflow may be placed on a dedicated branch with an exact branch filter and unique head-commit-message predicate. Its only execution path performs offline checks first, then the same **8-send** smoke using existing `ZAI_API_KEY` and the pinned coding route. It must be removed from that branch once the outcome is read; it must never be added to `main` or used as a default CI workflow. The ordinary dispatch-only workflow in this PR remains unchanged in trigger type. No result will be claimed until actual run logs/artifacts are inspected.

## Evidence reconciliation before any retry

The original one-shot report has now been supplied by the operator, but the
GitHub connector still cannot independently attest the push-triggered Actions
run. A bounded diagnostic exists and reports **eight HTTP 200 responses** and
**zero parseable model actions**. Do not automatically rerun it.

See `SMOKE_RECONCILIATION.md` for the exact launch/retirement commits,
Actions lookup link, recovery procedure and epistemic acceptance rules.
If a bounded technical artifact becomes available, validate it offline:

```bash
python scripts/audit_c3r_g1_smoke.py technical-qualification.json \
  --model glm-5.3 --route coding
```

This is a no-secret, no-network check for report structure and internally
consistent attempts/send accounting. Passing means
`structurally_consistent_unattested`, **not** validated provider execution,
scientific G1 learning or organizational G2 effect.

## 2026-10-22: uploaded one-shot report received

The previously missing technical report was provided as an uploaded ZIP.
See `ONE_SHOT_ARTIFACT_ANALYSIS_20261022.md` for the archived checksums,
verified cohort lock, **8/8 HTTP 200 reported**, 8/8 **empty**
`message.content` hashes, 16/16 output tokens spent in each request,
**0 accepted actions**, and **0 paired-analyzable qualification cases**.
This resolves artifact availability, not remote run or billing attestation.
No scientific G1/G2 result can be derived from zero accepted actions.

The construction fix for any *separately authorized future run* is:
GLM-5.3 forced thinking explicitly enabled, `reasoning_effort: low`,
`max_tokens: 512` (up to 4096 output tokens if all eight calls complete),
plus bounded `finish_reason`, optional reasoning-token-count and empty-output
metadata. There is **no automatic retry**. The historic eight-send report
remains unchanged.
