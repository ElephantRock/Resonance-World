# D2-vNext-Q1-A terminal-failure forensics

**Status:** post-outcome bounded diagnostic / no execution authority  
**Source run:** `35998227643`, attempt 1  
**Frozen result:** `D2-vNext-Q1-A1 — minimum_screen_completion_failure`  
**Successor construction issue:** #293

## Scope

This report uses only the frozen Q1-A canonical provider output, evaluation result, and four exact provider-shard outputs. It does not alter the consumed stream, infer scientific effects, or assign an upstream cause that the preserved evidence cannot identify.

Q1-A attempted 64 pairs and produced 25 complete evaluator-analyzable pairs and 39 failed pairs. Transport/accounting integrity and bounded terminal-failure observability passed.

## Shard reconciliation

| shard | complete / 16 | logical started | logical completed | logical failed | regeneration retries | terminal overrides | physical sends |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 421 | 411 | 10 | 5 | 27 | 466 |
| 1 | 7 | 506 | 497 | 9 | 8 | 37 | 567 |
| 2 | 5 | 421 | 410 | 11 | 7 | 25 | 470 |
| 3 | 7 | 526 | 517 | 9 | 5 | 32 | 575 |
| **total** | **25** | **1,874** | **1,835** | **39** | **25** | **121** | **2,078** |

For every shard, provider-budget blocks, unexpected-outbound blocks, logical-attribution mismatch blocks, and workers alive after drain were zero; transport hooks were restored.

Because each failed pair stops at its first fatal required logical call, the 39 failed pairs reconcile exactly to the 39 logical-call failures.

## Mixed-schema outcome

| shard | threshold complete | parity complete | interval complete | pairwise complete |
|---:|---:|---:|---:|---:|
| 0 | 2/4 | 2/4 | 2/4 | 0/4 |
| 1 | 2/4 | 3/4 | 2/4 | 0/4 |
| 2 | 2/4 | 1/4 | 2/4 | 0/4 |
| 3 | 1/4 | 4/4 | 2/4 | 0/4 |

`pairwise_order` therefore failed 16/16 across all four mixed-schema shards. Its zero completion yield is not a whole-shard schema/time confound and is not explained by one isolated shard.

## Fatal logical-call boundary

All 39 terminal failed-pair records have:

- the same registered failure class/type/fingerprint;
- first-attempt `parse_diagnostic=json_decode_failure`;
- first-attempt `runtime_exception=false`;
- first-attempt `hermes_completed=false`;
- exactly two physical provider sends on the fatal first attempt;
- exactly attributed clean transport.

The terminal adapter separates the fatal first attempts into:

| first-attempt adapter reason | count | retry eligible under frozen Q1 rule |
|---|---:|---|
| `final_response_empty` | 29 | no |
| `structured_parse_invalid` | 10 | yes |

All 10 parse-invalid fatal calls used the one permitted regeneration attempt. Their second attempts split evenly between `final_response_empty` (5) and `structured_parse_invalid` (5), and none produced an accepted exact completion.

Fatal phase bands were:

| phase band | fatal calls |
|---|---:|
| fresh | 4 |
| d40 | 18 |
| d80 | 8 |
| d160 | 9 |
| oracle | 0 |

The dominant `pairwise_order` fatal pattern was d40: 11 of its 16 terminal failures occurred in the d40 trajectory. Its first-attempt terminal reasons were 13 `final_response_empty` and 3 `structured_parse_invalid`.

## Regeneration accounting

The four shard counters record **25** format-regeneration attempts in total. Ten are the terminal retries described above. Therefore **15 retry-triggered logical calls successfully produced an accepted exact completion** before their containing pair either completed or, in some cases, failed later on a different logical call.

This establishes only that the existing single bounded regeneration mechanism had nonzero observed rescue efficacy in this run. It does **not** establish that regenerating after an empty terminal response will succeed, nor does it authorize such a change in the consumed Q1 stream.

## Causal ceiling

The evidence supports a narrower operational statement than the S2 artifacts permitted: the Q1-A failures are localized to **terminal structured-completion production/acceptance after clean provider HTTP transport and exact attribution**.

The evidence does not identify why the clean terminal invocation produced an empty or parser-invalid final response. Raw provider/model response content and intra-invocation token/iteration content were intentionally not retained. Accordingly, this report does not label the cause as a provider defect, model refusal, Hermes defect, or any other unsupported upstream mechanism.

## Prospective implication

Issue #293 isolates one fresh intervention for construction: retain the Q1 primary request path and exact parser, but make a strictly clean `final_response_empty` terminal result eligible for the same **single** independent format-regeneration opportunity already used for parser-invalid results.

The prospective trigger must remain fail-closed, include bounded `api_calls` observability, propagate no raw first-response content, add no third invocation, and preserve the existing parser and task prompts. Q2 must use a fresh namespace/cohort and a separate exact-candidate provider authorization.

This diagnostic report itself authorizes no provider/model execution, Q1-B execution, scientific-effect claim, Acceptance, registry action, D2e, deployment/publication, or Historical Substrate activation.
