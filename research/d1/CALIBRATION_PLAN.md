# D1-0 calibration plan — individual specialist capability reproduction

Status: **prospective development-only calibration; not confirmatory**.

Parent design: issue #160. Program base: `09da54404eca975c512137c70bb94d2a207e8178` (program PR #158).

H8 sequencing prerequisite is satisfied by the classifiable H8 result on authoritative workflow `31843357720`. D1 does not import H8 outcomes into its treatment or scoring logic.

## Purpose

D1-0 calibrates the first controlled capability-reproduction primitive before any fresh confirmatory D1 data are generated. It may be used to choose a prospective confirmatory sample size and convert a predeclared *relative product-fidelity convention* into an absolute score margin. It cannot itself support a capability-reproduction claim.

## Capability substrate

The initial capability is an objectively scored individual specialist in a three-skill deterministic task ecology.

Frozen D1-0 configuration:

```text
skills                 skill-a, skill-b, skill-c
population_size        8
source/destination cycles 96
target-skill demand    0.60
other-skill demand     0.20 each
exploration_rate       0.30
base_success           0.30
practice_gain          0.11 * sqrt(practice)
maximum_success        0.92
failure_learning       0.20 practice units
selection_holdout      64 trials
final_evaluation       256 trials
```

A successful development outcome adds one practice unit to the executed skill; a failed outcome adds `0.20`. Task allocation is exploratory with probability `0.30`; otherwise the most-practiced eligible agent is selected with deterministic opaque tie noise. This creates ecological specialization without assigning an occupational label to an agent.

## Development-only seeds

Exactly 64 independent Field-pair calibration seeds are frozen:

```text
10000, 10001, ..., 10063
```

For each pair the source and destination use separate derived environment seeds and disjoint agent identities. These seeds are permanently development data after the hosted calibration run and are forbidden from later confirmatory D1 evidence.

## Source → artifact → destination

For each pair:

1. a fresh source population develops under the task ecology;
2. a source specialist is selected on a separate selection holdout;
3. a `d1-capability-artifact-v0.1` is extracted from public source history and the frozen environment contract;
4. a fresh destination population with disjoint identities is developed only from the exported artifact contract;
5. a matched fresh no-development population is evaluated;
6. a private-state oracle copies source private practice only as a diagnostic upper bound.

The artifact includes:

- behavioral target inferred from public demand history;
- public evidence digest and source provenance;
- required task ecology;
- required substrate/success law;
- development and feedback protocol;
- resource requirements;
- stopping rule;
- heldout evaluation contract;
- explicit forbidden-transfer declaration.

The artifact may not expose source agent identity, reconstructive source/environment seeds, source private practice state, source conversation state, evaluator truth, or evaluation answers. Because this substrate is deterministic, exporting a source seed would permit reconstruction of source private state and is therefore explicitly forbidden. The destination execution path must consume the artifact contract rather than a source-private capsule.

## Calibration outcomes

D1-0 records per Field pair:

```text
source_developed_score
reproduced_protocol_score
fresh_no_development_score
private_state_oracle_score
source_uplift_vs_fresh
reproduced_uplift_vs_fresh
reproduced_minus_source
artifact bytes/hash
source/destination private-state hashes
source/destination identity-disjointness
forbidden-export audit
```

D1-0 estimates means and population SDs of the three causal differences. No p-value or confidence interval from these 64 seeds is a confirmatory result.

## Prospective planning convention

Before seeing hosted calibration output, D1 adopts a **90% reproduction-fidelity product convention** for planning P2: a reproduced capability should retain at least 90% of the source-developed uplift over a fresh baseline. This is classified `conventional`, not `derived_materiality`; it does not claim a natural or economic significance threshold.

D1-0 converts that relative convention into an absolute non-inferiority margin:

```text
margin = 0.10 * mean(source_developed - fresh_no_development)
```

The numerical absolute margin is therefore not frozen until the hosted development calibration is complete. The 90% fraction is frozen before that output is inspected.

P1/P2 planning uses one-sided alpha `0.05`, target power `0.90`, a normal-approximation planning calculation over Field-pair differences, and a **minimum n floor of 32 independent Field pairs**. The floor is itself conventional and exists to prevent a large deterministic effect from producing an implausibly tiny confirmatory campaign. Planning effects are calibration estimates, not SESOIs.

The confirmatory statistical implementation is *not* frozen by D1-0. A later pre-data lock must specify the exact CI/test implementation and sensitivity analysis.

## Integrity / stop conditions

The calibration workflow fails if:

- any source/destination selected identity is shared;
- any forbidden private/reconstructive field appears in the exported artifact outside the explicit forbidden-transfer declaration;
- the concrete source seed or selected source agent identity appears in the artifact payload;
- calibration records whether the artifact infers the source ecology's target specialization; an inference miss is a mechanism outcome, not an apparatus failure for future confirmatory execution;
- the destination does not use the artifact's required ecology/substrate/development contract;
- calibration seed count/range changes.

No provider credential is used. D1-0 is deterministic and must reproduce byte-identical output from the same code/config.
