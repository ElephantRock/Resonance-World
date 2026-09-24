# D2-vNext-S2 attrition forensics

**Status:** post-hoc diagnostic only; no consumed-stream rescue, provider execution, Acceptance, registry promotion, D2e execution, or Historical Substrate activation is authorized.

## Evidence basis

- Authoritative run: `35909017872`
- Canonical provider output SHA-256: `1419144f035ad1eafb3604f0a1859b134a2f9ddb280e1a04e4959d75e31042b2`
- Frozen evaluator result SHA-256: `f187defd4b27ca8f32858332c7e3448355d077a539574c2b97ffba1b919f4487`
- Pair ledger SHA-256: `30581c9c241092be6dcd7351931765f090d621ab1d38acac18d77795fe217dae`
- Frozen classification: `D2-vNext-S2-A0` — `acquisition_envelope_integrity_or_minimum_n_failure`
- Evaluator integrity: passed with no global, pair, or diagnostic defects.
- Transport integrity: passed; 14,509 physical sends under the 48,000 campaign ceiling; no transport defects.

## Exact reconciliation

| Schema | Attempted | Complete | Failed | Analyzable | Completion rate | 95% exact binomial interval |
|---|---:|---:|---:|---:|---:|---:|
| `threshold_at_4` | 96 | 60 | 36 | 60 | 62.5% | 52.0%–72.2% |
| `parity_pair` | 96 | 71 | 25 | 71 | 74.0% | 64.0%–82.4% |
| `interval_pair` | 96 | 58 | 38 | 58 | 60.4% | 49.9%–70.3% |
| `pairwise_order` | 96 | 16 | 80 | 16 | 16.7% | 9.8%–25.6% |
| **Total** | **384** | **205** | **179** | **205** | **53.4%** | — |

The four analyzable counts sum exactly to the 205 complete pairs. Because the evaluator recorded no pair defects, there is no second attrition step from complete to analyzable: each complete pair is analyzable for its one registered schema.

## Pair-failure class

All 179 failed pair records preserve the same bounded application-level terminal class:

```text
failure_class = provider_pair_failure
error_type    = RuntimeError
error_sha256  = 6c4a6ce59b69ad55cfd186ea90d43a07eb2f694cc17f54e284879eaa5304a6f9
preimage      = RuntimeError:D2-vNext-S2 logical call has no accepted exact completion
```

This is **not a transport-failure label**. Transport integrity passed. The frozen scientific client emits this RuntimeError when a required scientific logical call has neither an accepted first exact/effectively-completed response nor an accepted eligible format-regeneration response.

The failed-pair record does not retain the failing arm, phase, logical-call index, first-attempt diagnostic, or retry diagnostic. Those causal details are not recoverable from the canonical failed-pair rows and are intentionally left unknown.

## Shard-level accounting

| Shard | Schema | Complete/16 | Logical started | Logical failed | Format retries | Terminal overrides | Physical sends |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | `threshold_at_4` | 11/16 | 679 | 5 | 2 | 34 | 721 |
| 1 | `threshold_at_4` | 9/16 | 637 | 7 | 10 | 30 | 693 |
| 2 | `threshold_at_4` | 10/16 | 649 | 6 | 8 | 26 | 696 |
| 3 | `threshold_at_4` | 10/16 | 619 | 6 | 8 | 31 | 669 |
| 4 | `threshold_at_4` | 12/16 | 684 | 4 | 8 | 19 | 722 |
| 5 | `threshold_at_4` | 8/16 | 579 | 8 | 6 | 25 | 622 |
| 6 | `parity_pair` | 13/16 | 724 | 3 | 3 | 27 | 758 |
| 7 | `parity_pair` | 12/16 | 695 | 4 | 4 | 25 | 730 |
| 8 | `parity_pair` | 11/16 | 683 | 5 | 7 | 30 | 730 |
| 9 | `parity_pair` | 13/16 | 765 | 3 | 6 | 29 | 807 |
| 10 | `parity_pair` | 11/16 | 651 | 5 | 7 | 29 | 697 |
| 11 | `parity_pair` | 11/16 | 672 | 5 | 6 | 27 | 714 |
| 12 | `interval_pair` | 10/16 | 604 | 6 | 9 | 21 | 645 |
| 13 | `interval_pair` | 8/16 | 590 | 8 | 10 | 29 | 645 |
| 14 | `interval_pair` | 13/16 | 742 | 3 | 8 | 25 | 784 |
| 15 | `interval_pair` | 9/16 | 610 | 7 | 4 | 27 | 652 |
| 16 | `interval_pair` | 7/16 | 521 | 9 | 8 | 25 | 571 |
| 17 | `interval_pair` | 11/16 | 658 | 5 | 7 | 25 | 702 |
| 18 | `pairwise_order` | 2/16 | 236 | 14 | 3 | 36 | 292 |
| 19 | `pairwise_order` | 3/16 | 293 | 13 | 4 | 19 | 332 |
| 20 | `pairwise_order` | 3/16 | 254 | 14 | 3 | 21 | 294 |
| 21 | `pairwise_order` | 2/16 | 270 | 14 | 1 | 20 | 306 |
| 22 | `pairwise_order` | 4/16 | 331 | 12 | 3 | 25 | 374 |
| 23 | `pairwise_order` | 2/16 | 293 | 14 | 4 | 38 | 353 |

Every shard has zero budget blocks, zero unexpected-outbound blocks, zero attribution-mismatch blocks, zero provider workers alive after drain, and restored transport hooks. All downloaded shard JSON bytes reproduce the SHA-256 values recorded by the canonical aggregator.

## What the shard pattern establishes

- `pairwise_order` is not a one-shard incident: all six of its shards produced only 2–4 complete pairs out of 16, for 16/96 overall.
- The other schemas produced 8–12/16 (`threshold_at_4`), 11–13/16 (`parity_pair`), and 7–13/16 (`interval_pair`) per shard.
- The low `pairwise_order` yield is therefore distributed across its whole registered schema stratum. This supports **schema-associated heterogeneous attrition** as an observed pattern; it does not identify the mechanism causing it.
- There are 180 logical-call failures but 179 failed pairs. The single extra logical failure is the diagnostic oracle failure in `pairwise_order` pair 330; oracle failure is non-fatal to pair completion by design.

### Aggregate-implied location of fatal primary-call termination

The primary call sequence for a pair is fixed: fresh calls 1–4, developed-40 calls 5–13, developed-80 calls 14–27, and developed-160 calls 28–51; oracle calls 52–55 are diagnostic. Because a fatal primary failure stops the pair, shard totals permit an aggregate mean terminating-call index even though no individual failed pair preserves its terminal phase.

| Schema | Aggregate-implied mean fatal call index | Boundary |
|---|---:|---|
| `threshold_at_4` | 15.19 | exact aggregate mean |
| `parity_pair` | 11.40 | exact aggregate mean |
| `interval_pair` | 14.08 | exact aggregate mean |
| `pairwise_order` | 9.96–10.00 | bounded range because one completed pair had a caught oracle diagnostic failure |

These are aggregate constraints, not reconstructed per-pair failure phases. They must not be expanded into a more specific causal story.

## Prospective sizing sensitivity — diagnostic only

The table below asks a narrow hypothetical question: **if** the observed completion probability were a stable Bernoulli acquisition probability, how many attempts would be needed so that the probability of at least 88 complete/analyzable pairs reached a target? The second number uses the lower endpoint of the schema's 95% exact binomial interval as a stress input. These are not authorized sample sizes and are not evidence that the attrition process is stationary.

| Joint-schema design input* | Schema | Using observed rate | Using 95% lower-bound rate |
|---|---|---:|---:|
| per-schema clearance target 90% | `threshold_at_4` | 153 | 185 |
| per-schema clearance target 90% | `parity_pair` | 127 | 149 |
| per-schema clearance target 90% | `interval_pair` | 158 | 194 |
| per-schema clearance target 90% | `pairwise_order` | 595 | 1012 |
| per-schema clearance target 95% | `threshold_at_4` | 157 | 190 |
| per-schema clearance target 95% | `parity_pair` | 130 | 153 |
| per-schema clearance target 95% | `interval_pair` | 162 | 199 |
| per-schema clearance target 95% | `pairwise_order` | 616 | 1049 |
| per-schema clearance target 99% | `threshold_at_4` | 164 | 200 |
| per-schema clearance target 99% | `parity_pair` | 135 | 159 |
| per-schema clearance target 99% | `interval_pair` | 170 | 209 |
| per-schema clearance target 99% | `pairwise_order` | 656 | 1119 |

\*A project-level target that **all** schemas clear is stronger than a per-schema target and requires an explicit joint error/clearance contract. This table intentionally does not choose that contract.

The `pairwise_order` sensitivity is the decisive warning: simply scaling attempts under the current observed yield would require hundreds of attempted pairs for that schema. That is a reason to qualify the acquisition mechanism and improve observability before sizing a fresh confirmatory stream, not a reason to authorize a very large rerun.

## Prospective instrumentation requirement

A future qualification runner should persist a bounded terminal-failure record before collapsing a pair:

```text
pair_id
arm / phase / logical_call_index
first_attempt_completion_state
first_attempt_parse_diagnostic
retry_eligible
retry_used
second_attempt_completion_state / parse_diagnostic when applicable
accepted_exact_completion
transport_clean
logical_attribution_clean
```

Raw response content need not be retained if the experiment contract prohibits it; the diagnostic classes and hashes are sufficient to preserve the failure mechanism at a scientifically useful granularity.

## Next authorization boundary

The next executable experiment should be an **acquisition-qualification** experiment, not another confirmatory D2-vNext-S2 stream. Its contract must prospectively choose a per-schema acquisition target, a joint all-schema clearance target, attempted N by schema, send ceilings, stopping/replenishment semantics, and bounded failure observability. Provider/model execution remains a separate explicit authorization decision.
