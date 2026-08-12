# PIANO Phase 5B result: transferable structural-model memory

Status: **scientifically interpretable; advancement gate not met**.

This is the terminal confirmatory result for preregistration `glm5.2-transferable-institutional-model-v1`. The result must not be reclassified or tuned post hoc.

## Bound execution

- World revision: `51c215cec020ee326587c88136df66a6aee2b71f`
- Resonance Field revision: `e877bf03dbf6681ce7cbd98d984e73c032e911aa`
- Workflow run: `31650466893`
- Successful live job: `94296603257`
- Live artifact: `9162853556` (`piano-society-phase5b-live`)
- Live artifact digest: `sha256:98ea2ce8d84241bdcf6bd8d81a06b25ce635ddc92eef75629ede620903a0ed0d`
- Dataset digest: `4d0065d7f079cb3adc271edd595f868e187b86c71418ff1158283650ca780a05`
- Frozen source capsule SHA-256: `3db71e9b498605853454abe64c0937f032e8d91bf0500c76fe20b17c9e436ebd`
- Model snapshot: `glm-5.2`
- Paired units: 24 = 6 untouched confirmatory organizations × 4 missions
- Turnover: 100%
- Evaluation trials per arm/unit: 128, paired by common random numbers

Two earlier attempts of the same frozen workflow terminated without artifact creation because one Z.AI `speech` logical call exhausted the 12-attempt structured-output recovery contract while returning `speech` without `speech_action`. No partial dataset was inspected. The successful third attempt used the exact same World/Field revisions, source bytes, model, prompts, missions, seeds, ordering, retry policy, concurrency, and scientific gates.

## Frozen primary result

| Metric | Model reset | Model retained | Retained − reset |
|---|---:|---:|---:|
| Mission success rate | 0.2646484375 | 0.2646484375 | **0.0000000000** |
| Decisive forecast units | 14 | 14 | — |
| Forecast fidelity on decisive units | 1.00 | 1.00 | 0.00 |
| Cross-channel contradiction | 0.00 | 0.00 | 0.00 |
| Intent/action divergence | 0.00 | 0.00 | 0.00 |
| Outcome-report mismatch | 0.00 | 0.00 | 0.00 |
| Unsupported success claim | 0.00 | 0.00 | 0.00 |

Primary paired result:

- better: 0
- worse: 0
- ties: 24
- discordant: 0
- exact two-sided sign-test `p = 1.0`
- all six field-level mean effects: exactly 0.0

The preregistered advancement requirement of at least +0.03 mean success lift and `p <= 0.05` is therefore not met.

`advance_beyond_phase5b_transferable_memory = false`

No gate is relaxed after observing this result.

## Mechanism decomposition

The controller mechanism itself was intact:

- each arm had 14 decisive forecast units;
- forecast fidelity was 100% in both arms;
- contradiction and intent/action divergence were 0% in both arms.

However, **the retained structural posterior never changed the forecast-preferred strategy relative to the neutral reset prior on any of the 24 confirmatory units**. All 14 decisive units preferred the same strategy in both arms.

The model's executable action differed between arms on 6/24 units. All six differences occurred on forecast-tie units, outside the decisive-fidelity denominator. In every one of those six units, W5 `specialist` and `balanced` routing selected the exact same ordered member pair on the replacement roster. Consequently the environment received identical member/role assignments and identical trial seeds, producing identical outcomes by construction.

Across the full confirmatory set, specialist and balanced selected the exact same ordered pair in 10/24 units and the same unordered pair in 11/24. Thus fixed skill-pair contexts selected on two calibration organizations did not guarantee routing leverage on new organization rosters.

## Interpretation

Phase 5B improves the diagnosis from Phase 5:

1. A PIANO institutional controller can consume an organization-owned latent structural model with perfect forecast fidelity on decisive cases.
2. The structural posterior can be learned pre-turnover and recomputed against a replacement roster without leaking the hidden regime to the model.
3. But **fixed mission contexts selected on a small calibration set do not generalize decision leverage across fresh roster geometries**. On the confirmatory organizations, the neutral and retained structural forecasts never disagreed decisively about which routing policy to use.

Therefore the Phase 5B null is not evidence that structural institutional memory is useless. It is evidence that a transferable-memory capability test must ensure, before model inference and without reading confirmatory outcomes, that the current roster presents a real decision boundary between the candidate policies.

## Next experimental constraint

Any Phase 5C must remain a Phase-5 memory revision, use entirely fresh source organizations, and construct missions with a **preregistered roster-conditional algorithm** rather than fixed skill-pair contexts learned from two calibration organizations.

The constructor may read frozen pre-treatment capability state but not outcome samples or inherited-memory posterior. It should require that, on the replacement roster, the two structural hypotheses imply meaningfully different policy rankings and that `specialist` and `balanced` route to genuinely different member assignments. This turns Phase 5C into a capability test of whether inherited structural memory can resolve a decision that actually matters after complete turnover.
