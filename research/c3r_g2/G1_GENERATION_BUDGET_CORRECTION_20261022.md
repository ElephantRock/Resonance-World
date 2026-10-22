# G1: Correcting the artificial 512-token bottleneck — 2026-10-22

**Decision:** The original 512 output-token cap was an apparatus decision,
**not** a demonstrated GLM-5.3 limit. The 16-token and 512-token trial
records remain frozen diagnostics and cannot be reinterpreted as evidence
of failure to learn.

The public Z.AI GLM-5.3 release notes confirm that reasoning is mandatory,
and that `reasoning_effort=low` is supported. Independent providers list
a 1M-token context window and 128K/131,072-token maximum generated output.
The actual Z.AI route's accepted `max_tokens` range still needs direct
provider confirmation: bounds at other hosts are not a guarantee of native
Z.AI plan/endpoint entitlement.

- Primary: https://z.ai/blog/glm-5.3
- Third-party output specification: https://docs.mistral.ai/models/zai-glm-5-3
- Current model metadata reference: https://modelschemas.com/models/zai/glm-5.3

## Implemented, without any new live API calls

1. `ZaiStandardModelPort` defaults to **16,384 total output tokens**
   (mandatory reasoning plus final answer), but accepts a configured
   `max_tokens` value from **1 to 131,072**. This upper bound is an
   implementation safety bound; the chosen endpoint may reject it.
2. Bounded per-request timeout defaults to **180 seconds** (maximum
   300) rather than 30 seconds. Provider JSON response-body allowance
   rises from 64 KiB to **2 MiB**, permitting reasoning-bearing
   output to arrive and be processed. This does not bypass the
   no-retry, no-redirect, no-raw-content-logging or eight-send caps.
3. The existing eight-request technical calibration auditor and
   persistent campaign budget CLI now accept variable token budgets
   with the same guard; canonical request-body SHA256 commitments
   still include `max_tokens` and fail if mismatched.
4. The older `scripts/run_c3r_g1_live_smoke.py` explicitly accepts
   `--max-tokens` and `--timeout-seconds`, and reports the settings
   in its default **offline** preflight. Its manually dispatched
   workflow is updated with an explicit output budget and a longer
   overall job timeout. The workflow remains *manual*, does not run
   automatically, and is not deployable via a PR-only checkout until
   installed on GitHub's default branch.
5. Synthetic tests exercise budgets **16,384, 32,768, 65,536 and 131,072**
   through actual code paths, plus 32,768-token persistent-host
   reservation, offline CLI and budget-mismatch rejection. The older
   512-token historical regression fixtures remain in place.

## Minimal next experiment

Run a **single explicitly approved** bounded technical model probe
on the actual Z.AI endpoint, first confirming that the account/route
permits that work. An initial 16,384-token budget is a pragmatic test
starting point, not a best-known optimum or claim that the model
requires so many tokens. Record full finish reason, reported reasoning
and completion token usage, the final A/B yield and backend send count.
Increase the per-request budget only if the observed output metadata
shows truncation and provider limits permit an increase. Do not infer
G1 from formatting or answer-rate alone.

**No live Z.AI calls were made in this change.** No scientific
acceptance, pattern register promotion, historical result revisions,
provider-side billing/plan verification, or merge to `main`.
