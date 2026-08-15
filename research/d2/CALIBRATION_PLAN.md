# D2-0 calibration plan

Status: **prospective development-only calibration; never confirmatory evidence**.

Execution gate: no provider call until issue #165 records an independent D1/D1b acceptance-plane decision.

## Purpose

D2-0 exists only to choose a viable synthetic capability substrate, quantify stochasticity/variance, characterize model sampling, and derive the later confirmatory design. D2-0 cannot promote a mechanism and cannot be pooled with D2 confirmatory outcomes.

## Fixed conceptual substrate

Use an objectively scored hidden-policy decision task. Each case exposes a bounded observable feature vector and requires one action from a fixed action vocabulary. Hidden task truth is environment-owned and unavailable to agents.

Development episodes may return bounded objective outcome feedback. The fixed foundation model may generate/update a private strategy state between episodes. That private state is agent-local and non-exportable.

Source and destination Fields must use identity-disjoint agents, disjoint development examples, disjoint source/destination seeds, and a frozen generator contract. Confirmatory holdout cases are generated/frozen separately and are inaccessible to D2-0 development paths.

## Calibration arms

- `fresh`: objective only; no outcome-bearing development feedback.
- `description_only`: objective plus equal-call sham/unlabeled practice; no outcome-bearing feedback.
- `reproduced`: frozen candidate Capability Artifact plus destination-local development examples/feedback.
- `source_developed`: source-local development examples/feedback.

An optional private-state oracle is diagnostic only and must never enter product or promotion claims.

## Calibration outputs

D2-0 must report, without inferential promotion:

1. score distributions for all four arms;
2. source-development learning curves by development budget;
3. reproduced learning curves by development budget;
4. between-pair variance and paired-difference variance;
5. floor/ceiling diagnostics;
6. invalid-response rate;
7. logical-call and physical-attempt accounting;
8. source/destination development-example overlap rate, required to be exactly zero;
9. Capability Artifact leakage audit;
10. empirical information needed for power/minimum-N calculations.

## Model sampling characterization

Before choosing confirmatory sampling settings, run a frozen non-outcome calibration suite and record:

- unique-response rate;
- action entropy;
- repeat-response rate;
- valid-contract rate;
- between-replicate score variance;
- retry frequency and retry reasons.

Do not mechanically equate temperature/top-p semantics with another provider/model. D2 is initially single-model. Later model-generalization work must estimate within-model causal contrasts and compare effect heterogeneity rather than raw response distributions.

## Provider constraint

Initial candidate provider line: Z.ai. Candidate models are restricted to the project-authorized set `GLM-5.2`, `GLM-5-Turbo`, or `GLM-4.7`. The exact model and sampling settings must be frozen after D2-0 sampling characterization and before confirmatory data.

## Calibration success criterion

No numeric effect threshold is frozen here. D2 proper is allowed to proceed only if D2-0 demonstrates all of the following descriptively:

- the source arm develops a nontrivial measurable capability rather than remaining at floor;
- evaluation is not saturated at ceiling;
- reproduced and description-only arms are distinguishable enough to support a powered prospective P1 design;
- pair-level variation is estimable;
- valid structured outputs are sufficiently reliable for a mechanically scored campaign;
- the export boundary can be enforced exactly.

If those conditions are not met, revise the **development substrate only** while D2 remains pre-confirmatory, document every revision, rerun D2-0, and never reclassify calibration as confirmatory evidence.

## Confirmatory design handoff

D2-0 must output a calibration report containing the quantities used to choose:

- experimental unit;
- paired analysis structure;
- confirmatory minimum analyzable N;
- target power;
- P0/P1 effect threshold or explicit no-SESOI choice;
- P2 non-inferiority/materiality margin and provenance;
- CI/test family;
- multiplicity plan;
- fixed development/evaluation budgets.

Any numeric confirmatory threshold must be classified under the program threshold discipline as `derived_materiality`, `conventional`, or another explicitly justified evidentiary class.

No early stopping based on scientific outcomes is allowed in D2 proper.
