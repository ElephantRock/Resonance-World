# G1 prospectively registered GLM five-step inference diagnostic: effort × generation cap

**Date:** 2026-10-24. **Status:** FROZEN before physical sends; PR #310 remains Draft and scientific_acceptance=false. All work remains internal, without external auditor, custodian, serial approvals or automatic retries.

## Motivating observed failure

In the previous actual-model five-step pilot, GLM-5.3 supplied a syntactically accepted five-letter hypothesis in **14/24** prescribed source prompts and matched the hidden procedure in only **11/24**; the other 10 source outputs were classified as invalid_format. That report cannot determine whether the invalid results arose from generation cap exhaustion (finish_reason=length), response formatting, or provider errors, because the source summary did not retain sanitized finish and usage evidence. We must **NOT** retrofit or resend any of those physical attempts.

## Four-arm factorial, genuinely new matched tasks

A NEW single cohort freezes **eight** private five-step task contexts (four arithmetic, four text; balanced target bit positions), with precisely the SAME two corrected input/output training examples and the SAME prompt for **all four independently sent configurations** on each context:

| Condition | GLM-5.3 thinking | reasoning_effort | max_tokens |
|---|---|---|---|
| low-4096 | enabled | low | 4096 |
| low-8192 | enabled | low | 8192 |
| high-4096 | enabled | high | 4096 |
| high-8192 | enabled | high | 8192 |

This is a 2 × 2 prospective diagnostic on fixed underlying contexts, **not four independent task cohorts**, and not a test of persistent memory or a randomized controlled trial of abstract intelligence. Three new independently generated cohorts (01/02/03) yield **24 context units × 4 model calls = 96 prescribed model induction attempts**. Within a cohort context, the four calls use byte-for-byte identical two-example induction prompt and private target. Temperature 0; provider-side stochasticity, congestion and request order can still vary, and order is not blocked-randomized.

**Endpoint 1 (format or budget bottleneck):** proportion of 24 fixed context attempts producing a valid exact five-character A/B policy for each configuration. Responses are classified into MUTUALLY EXCLUSIVE: length_exhausted, non_stop_finish, invalid_format after stop, valid_wrong, valid_correct, or provider_error. A generation cap failure is only attributed to provider finish_reason=length (or a non-stop empty response whose reported completion tokens reach cap); we do not guess from absence of answer alone.

**Endpoint 2 (semantic inference):** proportion of 24 contexts yielding an exact correct five-character procedure, preserving invalids and errors in the denominator; among valid source responses, distinguish correct from valid-but-wrong. No controller repairs, reconstructs, retries or infers missing model policies.

**Operational secondary endpoints:** provider-reported prompt/completion/reasoning token sums with explicit missing counts; local monotonic per-call latency; error-class whitelist and sanitized finish_reason categories; valid output length (never actual generated text). These are observations, not reconciled vendor invoices, independently verified execution parameters or controlled equal-compute budgets.

## Execution, evidence and caveats

- Real GLM-5.3 Coding Plan route, thinking.type=enabled in every request; set reasoning_effort explicitly low/high, max_tokens explicitly 4096/8192, per-call 120-second timeout.
- Single private per-cohort owner-owned 0700 directory. Before ANY send, fsynced exclusive 0600 manifest freezes hidden target codes, examples, task IDs and all 32 logical indices, then each request takes an exclusive pre-send reservation O_EXCL. Max 3 in-flight calls per cohort and 2 concurrent cohorts; never retry a reserved/ambiguous send or rerun the same run ID. Each cohort independently closes to a private terminal file.
- Each 32-attempt cohort's public report keeps **exact index, condition, context-safe unit ID, masked prompt SHA256, class, finish_reason category, output length, latency and usage**. It never discloses raw model content, target codes, corrected source examples, hidden task operands or credentials. Uploaded artifacts include only these sanitized reports.
- For each context, record that all four prompt digests were identical. Cross-config comparison is **within context**; avoid treating 96 individual sends as 96 independent contexts. No grade cherry-picking, no dropping failures. Freeze definitions before any provider response.
- The previous five-step pilot under low-4096 is only historical reference; do NOT combine its data with this prospective matched-source factorial as a randomized baseline or claim paired replication.
- After genuine artifacts are captured, delete the one-shot workflow so it cannot accidentally dispatch paid reruns. No external audit or science gate is introduced. Never modify empirical prior reports.
- **Scientific interpretation:** isolating the effect of requested thinking intensity and token cap on *source response validity and correctness* informs the next G1 design. It does not establish model weight learning, autonomous strategy innovation, external memory transfer, calendar-delayed retention, G2 organizational learning or G3/G4 inheritance. scientific_acceptance=false; Pattern Register remains unchanged.

## Files

- scripts/run_c3r_g1_five_step_factorial_diagnostic.py
- tests/test_c3r_g1_five_step_factorial_diagnostic.py

Launch marker and workflow are separate after source + test CI passes.
