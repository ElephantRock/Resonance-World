# D2-vNext-Q2-A terminal-failure forensics

**Status:** post-outcome bounded diagnostic / no execution authority  
**Source run:** `36039847576`, attempt 1  
**Frozen result:** `D2-vNext-Q2-A1 — minimum_screen_completion_failure`  
**Successor diagnostic construction issue:** #296

## Scope

This report uses only the frozen Q2-A canonical provider output, evaluation result, and four exact provider-shard outputs. It does not alter the consumed stream, infer scientific effects, or assign an upstream cause that the preserved evidence cannot identify.

Q2-A attempted 64 pairs and produced 39 complete evaluator-analyzable pairs and 25 failed pairs. Transport/accounting integrity and bounded terminal-failure observability passed.

## Shard reconciliation

| shard | complete / 16 | logical started | logical completed | logical failed | regeneration retries | terminal overrides | physical sends |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 10 | 667 | 661 | 6 | 13 | 46 | 744 |
| 1 | 8 | 551 | 543 | 8 | 15 | 34 | 622 |
| 2 | 10 | 617 | 611 | 6 | 16 | 27 | 682 |
| 3 | 11 | 653 | 648 | 5 | 15 | 32 | 718 |
| **total** | **39** | **2,488** | **2,463** | **25** | **59** | **139** | **2,766** |

For every shard, provider-budget blocks, unexpected-outbound blocks, logical-attribution mismatch blocks, and workers alive after drain were zero; transport hooks were restored.

Because each failed pair stops at its first fatal required logical call, the 25 failed pairs reconcile exactly to the 25 logical-call failures.

## Mixed-schema outcome

| shard | threshold complete | parity complete | interval complete | pairwise complete |
|---:|---:|---:|---:|---:|
| 0 | 3/4 | 3/4 | 3/4 | 1/4 |
| 1 | 3/4 | 3/4 | 2/4 | 0/4 |
| 2 | 3/4 | 4/4 | 3/4 | 0/4 |
| 3 | 4/4 | 4/4 | 3/4 | 0/4 |

`pairwise_order` therefore failed 15/16 across all four mixed-schema shards. The failure concentration is not explained by one isolated shard.

## Terminal retry boundary

Every one of the 25 terminal failed-pair records used the single permitted Q2 regeneration attempt. Their first-attempt retry triggers were:

| schema | clean terminal empty | clean nonempty parser-invalid | total terminal failures |
|---|---:|---:|---:|
| `threshold_at_4` | 1 | 2 | 3 |
| `parity_pair` | 1 | 1 | 2 |
| `interval_pair` | 2 | 3 | 5 |
| `pairwise_order` | 13 | 2 | 15 |
| **total** | **17** | **8** | **25** |

First-attempt to second-attempt adapter outcomes were:

| first adapter reason | second adapter reason | count |
|---|---|---:|
| `final_response_empty` | `final_response_empty` | 13 |
| `final_response_empty` | `structured_parse_invalid` | 4 |
| `structured_parse_invalid` | `final_response_empty` | 4 |
| `structured_parse_invalid` | `structured_parse_invalid` | 4 |

Thus all 25 terminal retries remained within the same empty/parser-invalid terminal family; none produced an accepted exact completion.

## Pairwise concentration

`pairwise_order` is the dominant unresolved schema boundary:

- 15/16 pairs failed;
- 13/15 terminal failures were triggered by a clean terminal empty first result;
- 14/15 terminal failures occurred at `development2`;
- the `development2` terminal failures split into 12 clean-empty triggers and 2 parser-invalid triggers;
- the remaining pairwise failure occurred at `development5` and was clean-empty triggered.

This concentration is materially sharper than a generic whole-run completion problem and motivates structural observability specifically around the provider → Hermes → terminal-adapter boundary.

## Regeneration accounting

The four shard counters record **59** format-regeneration attempts in total. Twenty-five are the terminal retries described above. Therefore **34 retry-triggered logical calls produced an accepted exact completion** before their containing pair either completed or failed later at a different logical call.

Twenty-five such rescues are directly visible inside complete-pair call records. Their first-attempt triggers were:

| schema | clean terminal empty rescued | parser-invalid rescued | visible rescues |
|---|---:|---:|---:|
| `threshold_at_4` | 7 | 2 | 9 |
| `parity_pair` | 1 | 5 | 6 |
| `interval_pair` | 6 | 4 | 10 |
| `pairwise_order` | 0 | 0 | 0 |
| **total** | **14** | **11** | **25** |

The remaining nine successful retry-triggered logical calls occurred before an eventually failed pair reached a later fatal call; the canonical failed-pair summary does not preserve their trigger-class detail. This distinction prevents overclaiming the clean-empty rescue distribution.

The Q2 intervention therefore had nonzero observed rescue efficacy, including clean-empty rescue, but it did not resolve the dominant pairwise terminal boundary.

## Causal ceiling

The evidence supports the operational statement that the unresolved failures are localized to **terminal structured-completion production/acceptance after clean attributed provider transport**, with an especially strong `pairwise_order/development2` concentration.

The preserved Q2 data do not identify where the clean terminal empty originates. They do not distinguish:

1. provider response with no assistant content;
2. provider structural content that Hermes does not surface as a usable terminal response;
3. a Hermes terminal candidate lost or normalized to empty by the terminal adapter; or
4. a nonempty adapter candidate rejected by the exact parser.

Raw provider/model response content and the necessary structural boundary metadata were intentionally not retained. Accordingly, this report does not label the cause as a provider defect, model refusal, Hermes defect, terminal-adapter defect, or any other unsupported upstream mechanism.

## Prospective implication

Issue #296 constructs **Q3-D**, a diagnostic-only structural observability revision. Q3-D should preserve the Q2 behavior while adding content-minimizing metadata at provider-send, Hermes iteration/termination, and terminal-adapter boundaries. It must retain no raw prompt or response content and must not add a new rescue mechanism while diagnosis is in scope.

Any future Q3-D provider execution requires a separately frozen exact candidate, prospective fresh cohort/sample plan, explicit physical-send ceiling, and separate human authorization. This report itself authorizes no provider/model execution, Q2 rerun, Q2-B execution, scientific-effect claim, Acceptance, registry action, D2e, deployment/publication, or Historical Substrate activation.
