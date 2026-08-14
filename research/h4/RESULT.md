# H4 Result — Stochastic Successor Use of Accumulated Organizational History

Preregistration: #150  
Frozen World base: `392e9648fec9c4431fbf695cdd82a23c3ce11f48`  
Accepted exact scientific candidate: `42bc88e59707e2013cb8d2923fae0c0c2b0df56e`  
Model: `glm-5-turbo`  
Authoritative live run: `31761562214`  
Frozen-output evaluator run: `31761785993`

## Classification

**PASS — `historical_substrate_stochastic_successor_reasoning_pass`**

All registered Gates 0–12 are true. Production/default Historical Substrate remains disabled.

Authoritative result SHA-256:

`9743aed1e89a81ab0085ce6a1c2f96dada2b3c5c3b3b2fa5c47c933e470e1bc5`

Authoritative live-output SHA-256:

`4d1c2d2e0184ed8bf61fdcf4edabf904c1cfaf3403ae82bde3954ff7b4e369fc`

## Observed correctness

Correct decisions out of 36 pooled `(unit, replicate)` cells per generation/arm:

| generation | no history | flat accumulating | structured static | structured accumulating |
|---|---:|---:|---:|---:|
| g1 | 18/36 | 18/36 | 18/36 | 18/36 |
| g2 | 18/36 | 16/36 | 18/36 | 27/36 |
| g3 | 18/36 | 19/36 | 18/36 | **35/36** |

The g3 structured-accumulating result was directionally consistent in every stochastic replicate cohort:

| replicate | flat accumulating | structured accumulating |
|---|---:|---:|
| r1 | 6/12 | **12/12** |
| r2 | 7/12 | **11/12** |
| r3 | 6/12 | **12/12** |

At g3, the three registered reasoning families achieved structured-accumulating correctness of `12/12` for `temporal_latest`, `11/12` for `two_key_composition`, and `12/12` for `provenance_temporal`.

## Confirmatory contrasts

All four preregistered one-sided paired exact discordance tests were positive and survived Holm family-wise correction at `alpha = 0.05`:

| contrast | correctness | difference | discordance | raw one-sided p | Holm result |
|---|---:|---:|---:|---:|---|
| structured g3 vs flat g3 | 35/36 vs 19/36 | +0.4444 | 16–0 | 1.52587890625e-05 | reject |
| structured g3 vs no-history g3 | 35/36 vs 18/36 | +0.4722 | 17–0 | 7.62939453125e-06 | reject |
| structured g3 vs static g3 | 35/36 vs 18/36 | +0.4722 | 17–0 | 7.62939453125e-06 | reject |
| structured g3 vs structured g1 | 35/36 vs 18/36 | +0.4722 | 17–0 | 7.62939453125e-06 | reject |

Holm thresholds in ascending p-value order were `0.0125`, `0.016666666666666666`, `0.025`, and `0.05`; all four nulls were rejected.

## Execution integrity

The live provider panel completed all 432 registered logical cells with exactly 432 physical provider attempts: no transport/format retry was needed. Every cell was a fresh chat-completion request under the frozen `glm-5-turbo`, sampling, prompt, evidence-budget, and turnover contract.

The model-visible live output excluded Plane K, evaluator correct-action fields, the private evaluator sentinel, current-generation lessons, and future lessons. The evaluator confirmed canonical corpus equivalence, six-record budget parity, complete turnover, treatment-arm integrity, evidence-reference integrity, and the causal audit chain.

The exact live output is preserved by Actions artifact `9204825238` from run `31761562214` (artifact ZIP digest `sha256:47c7e4eb980fb70e3f11ca52075ae825211ef7f52c48a3e2932631674116d70c`). The deterministic confirmatory products are preserved by artifact `9204868100` from run `31761785993` (artifact ZIP digest `sha256:1967bb1861093ff51eedceac9fe63689dda48f0c92d2a4b07cb1189902fdd92f`). The frozen evaluator was executed twice against the same live bytes; `result.json`, `manifest.json`, and `audit.json` were byte-identical.

## Transparent orchestration record

Before the first model-exposed run, candidate `926363c271ae4401ee0b3a444a7edbd52bb5dd25` encountered a downloaded-artifact path mismatch and issued zero provider/model requests. That zero-exposure defect and the path-only repair were recorded prospectively in #150 before correction; all scientific fixtures and preregistered hashes remained unchanged.

After the authoritative 432-call live panel had been frozen, its same-run evaluator job encountered a shell-redirection directory error before executing the evaluator. This did not regenerate or change any model output. The failure and evaluation-only repair were recorded in #150 before evaluation. Run `31761785993` then checked out exact scientific candidate `42bc88e59707e2013cb8d2923fae0c0c2b0df56e`, re-verified all frozen input hashes, and evaluated the immutable live output twice.

## Scientific conclusion

H4 supports the following bounded claim: in this preregistered opaque-action benchmark, newly introduced stochastic successor model calls with no predecessor conversation or hidden state used bounded structured accumulating organizational history to make better held-out decisions after complete member turnover than successors receiving informationally equivalent unscoped flat history, a frozen structured snapshot, or no organizational history.

This result does **not** establish arbitrary-task organizational intelligence, production Historical Substrate readiness, generic sustainability, model-independent robustness, database superiority, or the value of PIANO institutional mechanisms. Those remain separate experimental questions.
