# C3R G1 — opt-in eight-send technical qualification runbook

**Status:** provider adapter constructed / offline verified (subject to CI) / no live run recorded.
**Authority:** user authorized continued implementation and provider qualification on 2026-10-21. This does not grant scientific mechanism acceptance, D2 campaign reruns, unlimited spending, or unrestricted access to credentials.

## Technical distinction

- `src/resonance_world/c3r_g1_zai_transport.py` implements an **explicitly enabled**, single-send-per-call Z.AI **standard API** connector against the single hardcoded URL `https://api.z.ai/api/paas/v4/chat/completions` (not the separate Coding Plan endpoint).
- It does **not** import Hermes, reuse D2 Q2/Q3 credentials/authority, or start network traffic on import.
- It reserves one physical-send slot in the shared in-process ledger **before** each request; exceptions, timeouts, HTTP non-200s, format errors and unknown outcomes still consume the slot. There is no retry, failover, redirect or tool access.
- At most **8** physical POSTs may be attempted in a single smoke process. This is a technical expenditure cap, not a promise of fixed monetary costs; model/provider prices and billable token accounting are outside its control.
- One 15-second timeout and up to 16 generated tokens are allowed per request by default. Max configured response tokens is 64.
- The existing GitHub repository secret is **`ZAI_API_KEY`**. The manually dispatched workflow passes its value into the CLI process as `C3R_ZAI_API_KEY` (an **environment variable alias, not a second GitHub secret**). Neither raw provider text nor the API key is preserved in reports; the adapter also redacts the key from its representation.
- The implementation uses Python's standard-library HTTP client with a pinned HTTPS endpoint and redirects disabled; it does not depend on, or modify, frozen Hermes SDK runtime behavior.
- A test double implementing the port is **not** a live model result, and the port's in-process ledger is **not** an external provider billing reconciliation.

## Offline preflight (default, does NOT access the network)

```bash
python scripts/run_c3r_g1_live_smoke.py
```

Outputs `offline_preflight_no_sends`, prospective cohort digest and an exact eight-send ceiling. It requires no secrets and does not authorize any provider request.

## Opt-in technical qualification

Only in an explicitly controlled execution environment, after verifying that the **existing `ZAI_API_KEY`** is valid for the **standard API** endpoint (not only a Coding Plan endpoint), selecting an explicit model, and reviewing costs:

```bash
# For local execution, map the existing ZAI_API_KEY privately to C3R_ZAI_API_KEY.
# GitHub Actions performs this aliasing automatically.
python scripts/run_c3r_g1_live_smoke.py --live --model YOUR_APPROVED_MODEL --max-sends 8
```

The operator should verify service access and intended billing plan before executing. The exact eight logical requests are: **4 source development, 2 learned qualification, 2 fresh qualification** under a single shared ledger. Once a physical request is attempted, its budget remains spent regardless of transport or parse outcome.

The example uses one opaque context and the same arithmetic ordering task schema, with the target ordering fixed at B. Its purpose is to test network/provider semantics, feedback separation, and analyzable yield, **not** to discover an effect. A fixed target may favor or disfavor an initial model policy; qualification is not powered or blinded from the operator.

The report always carries `technical_smoke_not_scientific_evidence`, the cohort digest, per-stage attempted/accepted/failure totals, per-call output digests, and transport reservation outcomes. Never store or expose credential values or raw provider outputs when sharing this report.

## Failure handling and stop rules

- Missing `--live`, model identifier or CLI environment variable `C3R_ZAI_API_KEY`: no network. The manual GitHub workflow injects it from the existing `secrets.ZAI_API_KEY`.
- Unexpected credential/endpoint/model availability: stop and report; do not silently substitute a D2 endpoint or a model.
- Eight reservations exhausted: fail closed; no ninth request, even if previous calls failed.
- HTTP 3xx/4xx/5xx, timeout, malformed response: no raw error body, no retries; attempt remains accounted.
- Invalid model action: no answer repair or hidden grader hint; it remains in the prescribed denominator.
- Provider authorization is **not** permission to interpret this smoke as confirmatory G1 acquisition or causal G2 organizational capability.
- Any later campaign needs an independently precommitted sample and evaluator, service-side or gateway-enforced attribution for physical sends, cost cap and observed yield, matched pre/post model sessions, inferential organization units, prospective power and pre-registered G1/G2 criteria.

## Where this runbook stops

The linked GitHub tool surface can write code and read CI results, but has no exposed workflow-dispatch action to start an authenticated experiment. The workflow must be made available from the default branch before GitHub Actions can list it for manual dispatch; this draft PR remains unmerged. The repository's CI intentionally runs only offline tests. A separate authorized operator environment with a private standard-API credential is required to execute this CLI. No provider response should be claimed until an actual bounded run log and accepted report exist.

References: Z.AI's official API documentation for standard `chat/completions` at `https://docs.z.ai/`, plus existing C3R `MODEL_PREFLIGHT.md` and `DESIGN_WORKSHEET.md`.

## Reusing the existing repository secret

The repository already has a secret named `ZAI_API_KEY`. **Do not create or rename it.** The workflow maps `secrets.ZAI_API_KEY` to the existing CLI variable `C3R_ZAI_API_KEY`. A repository-secret name appearing in GitHub Settings proves only that a value was stored; it does **not** prove the value is a valid standard-API credential, that the account is funded for the selected model, or that a technical run took place. Existing D2 experiments and their secret handling are unchanged. For governance, configure required reviewers on the `c3r-provider-qualification` environment before the first manual run; workflow names and environment labels alone do not ensure approvals.
