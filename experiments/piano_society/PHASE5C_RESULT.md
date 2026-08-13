# PIANO Phase 5C result: decision-relevant institutional memory

Status: **scientifically interpretable; advancement gate not met**.

This is the terminal confirmatory result for preregistration `glm5.2-decision-relevant-institutional-memory-v1`. It is a capability/stress test, not an estimate of natural mission prevalence. No frozen threshold is changed after observing the result.

## Bound execution

- World revision: `da24461e9244dbeb50d85e9fd1c35339726a49a9`
- Resonance Field revision: `e877bf03dbf6681ce7cbd98d984e73c032e911aa`
- Workflow run: `31653879702`
- Live artifact: `9163662793` (`piano-society-phase5c-live`)
- Live artifact digest: `sha256:e44cc271d688ada78c59a55410f028147c01e6e2954c923d2c42b56419943d4f`
- Dataset digest: `1cba37efee0d2dcba9c01010a2be684668c2a1c716f931e7dd0c4418ea7e2633`
- Frozen source capsule SHA-256: `b44926d70fe91ae3ad546351bd42096ad54a10d7d50eb954060e1bc56dcd1ea8`
- Model snapshot: `glm-5.2`
- Paired units: 12 distinct fresh organizations
- Turnover: 100%
- Evaluation trials per arm/unit: 256, paired by common random numbers
- Live execution completed on the first credentialed attempt.

## Frozen primary result

| Metric | Model reset | Model retained | Retained − reset |
|---|---:|---:|---:|
| Mission success rate | 0.2776692708 | 0.3030598958 | **+0.0253906250** |
| Decisive forecast units | 12 | 12 | — |
| Forecast fidelity | 1.00 | 1.00 | 0.00 |
| Cross-channel contradiction | 0.00 | 0.00 | 0.00 |
| Intent/action divergence | 0.00 | 0.00 | 0.00 |
| Outcome-report mismatch | 0.00 | 0.00 | 0.00 |
| Unsupported success claim | 0.00 | 0.00 | 0.00 |

Primary paired outcome:

- better: **9**
- worse: **0**
- ties: **3**
- discordant: 9
- exact two-sided sign-test: **p = 0.00390625**
- nonnegative unit effects: **12/12**

The preregistered primary effect-size floor was +0.03. The observed +0.025390625 therefore fails the advancement gate despite strong paired directional evidence.

## Mechanism result

- reset forecast reproduces the constructor's neutral preference: **12/12** (required 12/12)
- retained posterior matches target structure: **11/12** (required at least 10/12)
- retained forecast selects target policy: **9/12** (required at least 10/12)
- retained versus reset forecast preference changes: **9/12** (required at least 10/12)
- decisive forecast units: 12/12 in each arm (required at least 10)
- controller follows its own forecast: 100% in both arms (required at least 90%)
- report-mismatch delta: 0.0 (required at most +0.05)

Thus the run misses two frozen gates: mean effect size (+2.539 pp < +3 pp) and forecast reversal (9/12 < 10/12). All other gates pass.

`advance_beyond_phase5c_decision_relevant_memory = false`

## Per-unit causal effects

- `route-a`: +0.01953125
- `route-b`: 0.0
- `route-c`: 0.0
- `route-d`: +0.0234375
- `route-e`: +0.03515625
- `route-f`: +0.02734375
- `route-g`: +0.01171875
- `route-h`: +0.0390625
- `route-i`: 0.0
- `route-j`: +0.02734375
- `route-k`: +0.0703125
- `route-l`: +0.05078125

There are no harmful units.

## Three forecast-reversal misses

The three zero-effect units are exactly the three cases where retained memory failed to overturn the neutral roster-only forecast:

### route-b — weak role-specific posterior

- target: `role_specific` / `specialist`
- reset preference: `balanced`
- retained posterior: role-specific **0.51350**, cross-coverage 0.48650
- retained preference: `balanced`
- posterior role-specific probability required to flip the registered roster forecast: approximately **0.60064**

### route-c — wrong structural posterior

- target: `role_specific` / `specialist`
- reset preference: `balanced`
- retained posterior: role-specific **0.45195**, cross-coverage 0.54805
- retained preference: `balanced`
- role-specific probability required to flip the forecast: approximately **0.58344**

This is the sole unit whose retained posterior points in the wrong structural direction.

### route-i — insufficient cross-coverage certainty

- target: `cross_coverage` / `balanced`
- reset preference: `specialist`
- retained posterior: role-specific **0.21791**, cross-coverage 0.78209
- retained preference: `specialist`
- role-specific probability must fall below approximately **0.18785** (cross-coverage above ~0.81215) to flip this roster forecast.

## Interpretation

Phase 5C materially improves on Phase 5B. Once the task constructor guarantees a genuine routing decision boundary, inherited structural memory causes a positive outcome effect with no observed harm: 9 improvements, 3 ties, 0 regressions, paired `p = 0.00390625`. The PIANO controller is not the bottleneck: forecast fidelity, cross-channel consistency, and execution reporting are all perfect.

However, the experiment does **not** validate the institutional-memory advancement claim under the frozen standard. The mean effect falls 0.461 percentage points short of the +3 pp floor, and the learned structural posterior is not informative enough to reverse the neutral decision in three organizations.

The remaining uncertainty is therefore an **information-quality problem in institutional memory formation**, not an action-selection or task-geometry problem.

## Next experimental constraint

A valid follow-up should not rerun these 12 organizations or tune their thresholds. It should use entirely fresh organizations and treat memory information quality as an explicit independent variable. The clean next question is a dose-response one:

> How much organization-owned formation evidence, and how much structural identifiability in that evidence, are required before persistent institutional memory reliably changes a consequential post-turnover decision and produces at least the registered +3 pp outcome lift?

That follow-up should preregister the evidence/identifiability levels before any fresh confirmatory outcome is observed, preserve the same PIANO controller and environment law, and keep Phase 5C as the terminal result for this capability design.
