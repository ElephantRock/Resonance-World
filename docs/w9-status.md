# W9 Criticality-Aware Regenerative Capability Market — Status

Status: **COMPLETE — REGENERATIVE ALLOCATION NOT SUPPORTED**

W9 tested whether source-criticality-aware allocation, mission-level capability leasing,
pre-departure functional redundancy, and identified coalition mechanisms could remove the
source-sustainability / organization-service trade-off retained from W8 without changing
Resonance Field or allowing regulatory state into mission-success laws.

The registered regenerative claim is **not supported**. The only positive nested claim
that replicated is calibration of the public criticality estimator:

- `replicated_calibrated_criticality_pricing`: **true**
- `replicated_tradeoff_reduction`: **false**
- `replicated_sustainable_capability_leasing`: **false**
- `replicated_regenerative_allocation`: **false**

W9 therefore closes as a replicated negative/mixed result. Failed mechanisms were
retained as failures and were not retuned or promoted into the integrated regime.

## Frozen scientific boundary

- Resonance Field pin: `2a85739603ebac86f451b90733229782c0d45ce0`
- Resonance Field source modification: **none**
- discovery Fields: `3611, 3731, 3851, 3971, 4091`
- unseen replication Fields: `4211, 4331, 4451, 4571, 4691`
- 12 agents per Field
- 512 matched trials per evaluated condition unless otherwise preregistered
- source-sustainability bound: mean realized source loss `<=2 pp`
- organization non-inferiority band: generally `-2 pp`
- required source-loss reduction for the allocation/integrated claims: `>=50%`
- exact private `practice_by_skill` unavailable to recruitment/allocation
- regulation, lease identity, criticality score, redundancy state, payment, coalition
  identity, and budget state remained outside mission-success probability laws
- no discovery failure, threshold, seed, estimator law, comparator, or synthesis rule was
  retuned after outcomes existed

## W9-00B — Public marginal-source-cost estimator: PASS / REPLICATED

The estimator uses the frozen public selector-derived probability model and a conservative
budget score `MSC_budget = MSC_hat + 1.645 * 0.70 pp`.

Discovery classification: **`calibrated_source_cost_estimator`**

- MAE: **0.2832602348748846 pp**
- signed bias: **-0.1605426728259532 pp**
- Spearman rho: **0.7594820900342301**
- high-cost safe rate: **0.9333333333333333**
- calibration slope: **0.9518272274711025**
- calibration intercept: **0.1798937562422811**

Unseen replication classification: **`calibrated_source_cost_estimator`**

- MAE: **0.3458448850239709 pp**
- signed bias: **-0.16760685101992465 pp**
- Spearman rho: **0.606374720885561**
- high-cost safe rate: **0.9333333333333333**

The replication rho remains above the preregistered `0.60` boundary, so calibrated
criticality pricing is the one positive W9 nested claim that replicated.

## W9-01 — Criticality-aware recruitment: FAIL / REPLICATED

Discovery classification: **`criticality_allocation_ineffective`**

- W7 unrestricted organization success: **45.18229166666667%**
- W7 unrestricted source loss: **3.1656409894904503 pp**
- W8 cap-2 organization success: **48.69791666666667%**
- W8 cap-2 source loss: **2.2828211006628885 pp**
- criticality allocation organization success: **24.869791666666664%**
- criticality allocation source loss: **0.2592175532970553 pp**
- criticality allocation contracts: **5** versus **9** unrestricted

The criticality allocator reduced source loss by about 91.8%, but organization
non-inferiority failed by roughly 20 pp. The fixed `0.70 pp` estimator SE creates a
`1.1515 pp` one-sided uncertainty surcharge per first contract, so the `2 pp` source
budget becomes highly restrictive.

Unseen replication classification: **`criticality_allocation_ineffective`**

- unrestricted organization success: **42.7734375%**
- unrestricted source loss: **2.570742855074357 pp**
- cap-2 organization success: **44.40104166666667%**
- cap-2 source loss: **2.0356437964399188 pp**
- criticality organization success: **22.005208333333336%**
- criticality source loss: **0.27403733680031017 pp**

The source-protection gates pass again; organization non-inferiority fails again.
`replicated_tradeoff_reduction` is therefore **false**.

## W9-02 — Mission-level capability leasing: MIXED / NOT REPLICATED AS A POSITIVE CLAIM

Discovery classification: **`leasing_switching_fragile`**

- permanent organization success: **79.87738715277779%**
- permanent source loss: **3.165640989490559 pp**
- zero-recovery lease organization success: **79.87738715277779%**
- zero-recovery source loss: **-3.119489941777708 pp**
- one-window recovery organization success: **79.87738715277779%**
- one-window recovery source loss: **2.512404169219193 pp**

Zero-recovery leasing passed, but the preregistered one-window recovery sensitivity did
not.

Unseen replication by itself crossed the robust gate:

- permanent organization success: **78.94422743055556%**
- permanent source loss: **2.5707428550744993 pp**
- zero-recovery source loss: **-3.294741430892092 pp**
- one-window recovery source loss: **1.9641251872372116 pp**

The replication recovery result is only about `0.036 pp` inside the `2 pp` threshold and
cannot rescue the discovery failure. Under the frozen nested rule,
`replicated_sustainable_capability_leasing` remains **false**.

## W9-03 — Pre-departure functional redundancy: FAIL / REPLICATED

Discovery classification: **`redundancy_not_efficient`**. No portfolio mechanism was
eligible for W9-05.

Discovery:

- no-preparation: organization **28.190104166666668%**, source loss
  **0.2592175532970553 pp**
- matched control: organization **30.143229166666668%**, source loss
  **0.6987145695838559 pp**
- portfolio: organization **23.828125%**, source loss **0.14948282938114454 pp**
- portfolio usable contracts: **5**

Unseen replication classification: **`redundancy_not_efficient`**

- no-preparation organization: **15.364583333333334%**; source loss
  **0.27403733680031017 pp**
- matched-control organization: **41.92708333333333%**; source loss
  **0.46658192243468344 pp**
- portfolio organization: **42.7734375%**; source loss **0.19254458563437993 pp**
- portfolio development compute: **720 resident-agent-cycles**

Source protection is strong, but the registered efficient concurrent-service claim does
not pass. `P` remains ineligible.

## W9-04 — Coalition mechanism identification: no mechanism selected

The complete frozen `2^4` discovery assay tested structure-aware selection (`D`), role
specialization (`R`), one-bit coordination (`C`), and cross-source candidate restriction
(`V`).

Discovery main effects:

- `D`: **+0.3255208333333333 pp**
- `R`: **+1.5625 pp**
- `C`: **0.0 pp**
- `V`: **0.0 pp**

No factor met the preregistered `>+2 pp`, mission-family, and Field-consistency rule; no
qualifying interaction entered the downstream mechanism. Frozen `K = none`.

Unseen replication remained diagnostic only:

- `D`: **+0.13834635416666666 pp**
- `R`: **+0.6266276041666666 pp**
- `C`: **0.0 pp**
- `V`: **-0.13834635416666666 pp**

`K` remains empty.

## W9-05 — Integrated regenerative market: FAIL / REPLICATED

Because W9-01, W9-02, W9-03, and W9-04 selected no eligible mechanism in discovery, the
frozen selected W9-05 regime is the empty set and is operationally the W7 unrestricted
regime. Failed diagnostic mechanisms are reported but are not reinterpreted as W9
successes.

Discovery classification: **`integrated_static_gate_failed`**

- selected/W7 organization success: **79.87467447916666%**
- selected/W7 source loss: **3.165640989490559 pp**
- organization-outcome inequality SD: **0.7551568843226869 pp**
- contracts: **9**

Organization, inequality, and upstream-eligibility gates pass. The `<=2 pp` source bound
and `>=50%` source-loss-reduction gates fail.

Unseen replication classification: **`integrated_static_gate_failed`**

- selected/W7 organization success: **78.79231770833334%**
- selected/W7 source loss: **2.5707428550744993 pp**
- organization-outcome inequality SD: **1.985310171446097 pp**
- contracts: **9**

The same two source gates fail. No failed constituent was promoted into the selected
regime.

## W9-06 — Long-horizon regenerative economy: FAIL / REPLICATED

The accepted accounting law defines Developmental Efficiency as source-accessible
frontier capability change divided by source development/training compute. A zero
denominator is **undefined/null**, not infinity, and cannot satisfy the registered `>=20%`
improvement gate.

Discovery classification: **`long_horizon_gate_failed`**

Selected/W7:

- organization success: **78.65397135416667%**
- source loss: **2.93804390273108 pp**
- source-accessible capability growth: **-0.3875840399809345**
- normalized World stock growth: **-0.9981878507021908**
- source development compute: **0**
- Developmental Efficiency: **null**
- service efficiency: **0.30449780576907415**

Unseen replication classification: **`long_horizon_gate_failed`**

Selected/W7:

- organization success: **77.65299479166667%**
- source loss: **2.4070210108197023 pp**
- source-accessible capability growth: **-0.17385959621218028**
- normalized World stock growth: **-0.9981331586374954**
- source development compute: **0**
- Developmental Efficiency: **null**
- service efficiency: **0.3031002645831297**

The selected regime therefore fails source sustainability, positive source capability
growth, compute-normalized stock growth, and the Developmental Efficiency comparison.
`replicated_regenerative_allocation` is **false**.

## W9-07 — Entirely unseen replication acceptance

The accepted replication head was:

`eaaa0c013cd878a5d0e1afa88bfc6d54e90ae371`

Dedicated exact-head workflow:

- run: `31654273741`
- primary reproduction: **PASS**
- independent reproduction: **PASS**
- downstream byte-comparison acceptance job: **PASS**
- primary artifact: `9163835188`
- primary artifact digest:
  `sha256:550da9bfb7ad64dfde8f2c8c48e4ba75de28fb25097152455d0cd3abd6c0487a`
- independent artifact: `9163824319`
- independent artifact digest:
  `sha256:e8042d2e9591864b244485c2a79472b2877636ca70b486834bb3f83701cbbd16`

The authoritative files were byte-identical across the two isolated reproductions:

- W9-00B: `24fe37070bef8df3484876638df870bc8f98ebc3fce18a6b149242cf24a2cec6`
- W9-01: `0351532e8513b323a90fb22ddf157f6316efc73962ab5d4b6946df4cf7abcd11`
- W9-02: `1cbfa3abf795fb8e987b6c74ba584a149571609a8dcf8909ae1e1176f95fb269`
- W9-03: `8c86445c589e82016c4e494f5fd1c0acbf1e0bdb750920acec5de997686f7535`
- W9-04: `7e5c1698bdc59efb429f47c81718f3d6c0c7daba575068ab12aa8dd69503edac`
- W9-05: `cbd0ac389e581c7fa1cc5616de10eccc5fffd39fd91f14b1589d7ac6efed650b`
- W9-06: `9e37f426c15fd0dc049fc9da07d25f48dcc6092c1967714b9e90c6274c42f562`
- W9-07 synthesis: `0400ad83885dc81a0c8a139431f98545b0a948e1698a4522631fc8e413c10c44`
- manifest: `da518137aaf23fdfc679f7a5b227f36bb9f4e81497bb1f2f6886adca4defe81e`

Fresh exact-head Codex review reported no major issues. The W9-07 implementation was
squash-merged through PR #105 as:

`410006144e930fc0a52ffea9c2fae70fb6a58d5b`

## Interpretation

W9 establishes that a public-evidence marginal-source-cost estimator can be calibrated
and can strongly suppress measured source damage, but the frozen uncertainty-priced
allocation sacrifices too much organization service. Mission-level leasing is promising
but discovery-sensitive to switching/recovery cost. Pre-departure portfolio development
protects source capability but does not establish an efficient concurrent service regime.
No coalition factor met the registered mechanism-selection rule. Consequently the
integrated regime remains empty and cannot satisfy the static or long-horizon regenerative
gates.

The result is evidence about a persistent design constraint, not permission to retune the
failed mechanisms: source protection alone is insufficient. A successful successor must
jointly preserve frontier organizational performance, source viability, and long-horizon
capability regeneration under a preregistered accounting law.
