# W4 Campaign Status

Status: **PARTNER-SPECIFIC COORDINATION CAPITAL REPLICATED IN THE W4A EXTENSION**

- Parent issue: #26
- Experiment count: 7
- Discovery source Fields: 5 x 12 agents = 60 fresh agents
- Held-out discovery Fields: 2
- Replication source Fields: 3 x 12 agents = 36 unseen agents generated after discovery
- Deep formation: 12 fixed-pair episodes
- Communication: 1 bit for every pair condition
- Primary threshold: 2 absolute percentage points
- Pinned Resonance Field revision: `0914a21249261fe61e02c5191f4a36df416c672f`

## Validation record

First valid full W4 campaign:

- Actions run: `31473784331`
- W4 evidence artifact: `9094462884`
- artifact digest: `sha256:9efb08d116edf0e52041bcdb22c85ac6c33f2d4ceb51982d7e251b1f7ce177d4`

Post-compliance reproducibility campaign:

- Actions run: `31474203291`
- W4 evidence artifact: `9094677225`
- artifact digest: `sha256:70657d6c35ccf731d77ef9a6dc78b910664610e150b6a1f9aea6b58fbeba8a6e`
- discovery JSON reproduced byte-for-byte
- W4-07 replication JSON reproduced byte-for-byte

W4-02 checkpoint-completion run:

- Actions run: `31474203320`
- artifact: `9094576906`
- artifact digest: `sha256:0443f589dbedd40c58f54c531aab7c9c5014721794aa8e7ceeb14976f134a10e`

## W4-01 — fixed-pair formation depth

The preregistered 0/2/6/12 depth arms produced a non-monotonic but positive deep-minus-zero effect:

- depth 0: 17.01%
- depth 2: 18.00%
- depth 6: 20.17%
- depth 12: 19.36%
- depth 12 minus depth 0: **+2.34 percentage points**

Deep formation remained fixed at 12 episodes; the stronger depth-6 point was not used to retune W4-03 or W4-07.

## W4-02 — coordination learning curve

The initial W4 implementation reported only the four formation-depth arms even though the campaign had preregistered auxiliary checkpoints 1/4/8. This was identified after the first full campaign. A separate compliance measurement was then added without changing any W4-03/W4-07 mission, threshold, treatment depth, assignment rule, environment law, or source identity.

All registered checkpoints were subsequently materialized:

- depth 0: 15.63%
- depth 1: 17.33%
- depth 2: 18.72%
- depth 4: 17.77%
- depth 6: 18.49%
- depth 8: 17.48%
- depth 12: 18.75%
- depth 0 to 12: **+3.13 percentage points**

The curve is non-monotonic. W4 therefore supports repeated-experience improvement at the registered endpoint but not a monotonic learning-law claim.

## W4-03 — C1/C2/C3/C4 held-out factorial

Held-out Fields: 491 and 612.

Pooled classification: **`partner_specific`**.

- partner-specific difference-in-differences effect: **+7.36 percentage points**
- general-teamwork effect `C2 - C3`: **+1.35 points**
- partner-specific effect positive in 2/2 held-out Fields
- general-teamwork effect positive in 1/2 held-out Fields

Field 491:

- partner-specific effect: +2.99 points
- general-teamwork effect: +8.03 points
- pre-existing original-vs-rotated compatibility delta: -1.26 points

Field 612:

- partner-specific effect: +11.72 points
- general-teamwork effect: -5.34 points
- pre-existing original-vs-rotated compatibility delta: -12.59 points

The preregistered difference-in-differences contrast corrects for those substantial pre-treatment compatibility differences.

## W4-04 — relationship reset

On the original held-out pairs, pair-specific reset while preserving general teamwork did **not** reduce performance on average:

- pooled full-minus-pair-specific-reset effect: **-3.73 points**
- pooled general-teamwork-on-original-pair effect over full coordination reset: **+11.78 points**

This means the W4-03 partner-specific factorial result should not be interpreted as a simple scalar benefit residing in every pair-specific state component. The causal value depends on pairing/context and is not captured by a monotonic "more pair state is better" rule.

## W4-05 — state decomposition

- pair-memory contribution: **+3.47 points**
- partner-model contribution: **-4.71 points**

The positive held-out relationship signal is therefore more consistent with useful pair-shared episodic history than with the current partner-role predictor. The partner-model component can be neutral or harmful under the tested controller.

## W4-06 — transfer boundary

On novel task combinations that preserved the learned coordination-context labels:

- partner-specific effect: **+6.84 points**
- general-teamwork effect: **+0.52 points**

When the coordination contexts themselves were renamed to unseen contexts:

- partner-specific effect: **-0.39 points**
- general-teamwork effect: **0.00 points**

The discovered coordination capital is therefore **context-bound**. W4 does not establish context-free social skill.

## W4-07 — unseen replication

Replication source Fields 733, 854 and 975 were generated only after discovery completed. The frozen protocol was then applied without retuning.

Pooled replication classification: **`partner_specific`**.

- partner-specific effect: **+8.46 percentage points**
- general-teamwork effect: **-0.88 points**
- partner-specific effect positive in 3/3 unseen Fields
- general-teamwork effect positive in 1/3 unseen Fields
- qualitative classification matches discovery
- preregistered replication gate: **PASS**

Field-level classifications were heterogeneous:

- Field 733: `partner_specific`, partner effect +23.65 points
- Field 854: `neither`, partner effect +1.35 points
- Field 975: `general_teamwork`, general effect +12.46 points

The pooled replicated result is therefore not a claim that every society develops the same social phenotype. It is evidence that the preregistered partner-specific contrast survives across the unseen cohort in aggregate, with positive partner-effect sign in all three Fields.

## Scientific interpretation

Within the W4A/W4A.1 deterministic joint-learning extension:

> repeated fixed-pair experience can create **partner-specific, context-bound productive coordination capital** that survives transfer to novel task content sharing the learned coordination contexts and reproduces on post-freeze source populations.

W4 does **not** show:

- universal partner-specific capital in every Field;
- a robust partner-independent general teamwork skill;
- context-free relationship portability;
- spontaneous pair-state emergence in the original Resonance Field runtime;
- general LLM-agent social cognition.

The environment outcome law remained blind to relationship/teamwork state throughout W4. Relationship state affected decisions only; no direct relationship-history success bonus was used.

Resonance Field was not modified by W4. The relationship-learning mechanisms live in the explicitly documented Resonance World W4A/W4A.1 architectural extension.
