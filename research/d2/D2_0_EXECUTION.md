# D2-0 execution lock — stochastic model-mediated capability calibration

Status: **development-only calibration apparatus frozen before provider execution**.

D2-0 is not confirmatory evidence and cannot promote the Mechanism Registry. Its only purpose is to determine whether the proposed stochastic individual-agent substrate is viable enough to support a later preregistered D2 test.

## Authority prerequisite

Issue #165 is complete. The independent Z.AI `glm-5-turbo` acceptance reviewer authorized both D1/D1b transitions, and PR #170 landed `d1_capability_reproduction` as `internally_replicated` on `main` at `31cfd4f216dc1c98bdd97af5f174f7298d412cb6`.

Production/default Historical Substrate remains OFF.

## Frozen D2-0 cohort

- 8 calibration Field pairs, indices `0..7`.
- private policy seed namespace begins at `720000`, with a stride of 10 per pair;
- source development RNG = pair seed + 1;
- destination development RNG = pair seed + 2;
- calibration evaluation RNG = pair seed + 3;
- 16 source-local development cases per pair;
- 16 destination-local development cases per pair;
- 24 held-out calibration evaluation cases per pair;
- source and destination development feature vectors must have exact overlap count 0;
- all development and calibration evaluation feature vectors must have exact overlap count 0.

The future confirmatory D2 cohort is **not generated or inspected in D2-0**. A later confirmatory plan must use a separately frozen seed/identity namespace and holdout contract.

## Hidden-policy task family

Each Field pair receives one fixed environment-owned policy. Cases expose four integer features `f0..f3`, each in `0..7`, and require exactly one action from:

```text
KAPPA | MICA | ORBIT | VELA
```

The private policy is selected from a frozen six-member family of parity/threshold compositions over the four features, combined into two latent bits, pair-specific bit flips, and a pair-specific opaque action permutation. The actual family, flips, permutation, correct actions, and truth token are never included in a Capability Artifact or model-visible task description.

All arms may know the generic task-family description. This prevents task-schema knowledge itself from being confounded with outcome-bearing development.

## Development protocol

Development proceeds in two local batches of 8 cases.

For `source_developed` and `reproduced`, the agent receives objective local feedback after each development batch containing its chosen action, correctness, and the correct action. It may update a concise private strategy between batches. That strategy is never exported to another Field and is persisted in the research output only by SHA-256 digest, not plaintext.

For `description_only`, the agent receives the same number of logical calls and the same destination-local practice cases, but only unlabeled practice history: its prior case, features, and chosen action. No correctness or correct action is supplied.

`fresh` receives no development calls and answers only the held-out calibration evaluation batch.

Final calibration evaluation occurs after 16 development episodes. Source/reproduced evaluation prompts may incorporate the second batch's local feedback while updating private strategy internally. Description-only receives only unlabeled second-batch history. No evaluation feedback is returned.

## Capability Artifact v0.2

The public Artifact is constructed only after source development. It may include aggregate source-public learning evidence, the behavioral objective, generic task ecology, development schedule, feedback contract, private-memory interface, provider/resource requirements, stopping rule, evaluation contract, dependencies, and provenance.

It may not contain source identity, conversation state, private strategy/memory, source examples, source/environment seeds, hidden policy/truth, evaluator answers, or any calibration/confirmatory answer key. Every exported Artifact must pass `scripts/d2_artifact_core.py` against the concrete source identity, seeds, example IDs, and private truth token before the reproduced arm may run.

## Provider and sampling characterization

Provider line: Z.AI.

D2-0 development candidate:

```text
model = glm-5-turbo
temperature = 0.8
thinking = disabled
response_format = json_object
```

This is a **calibration setting, not the frozen D2 confirmatory setting**.

Before the paired development panel, a fixed 8-case sampling suite is repeated 6 times at each temperature:

```text
0.4, 0.8, 1.0
```

The calibration report records unique-response rate, repeat-response rate, action entropy, valid-contract rate, between-replicate score variance, physical attempts, retry frequency, and retry reasons. D2 proper may choose the final model/sampling contract only after inspecting this development-only characterization.

## Logical-call accounting

Per Field pair:

- `source_developed`: 3 logical calls;
- `reproduced`: 3 logical calls;
- `description_only`: 3 logical calls;
- `fresh`: 1 logical call.

The `reproduced` and `description_only` equality is a hard integrity condition. Transport retries are physical attempts, not additional logical treatment calls, and are fully recorded.

The sampling suite adds 18 development-only logical calls. The frozen D2-0 design therefore contains 98 logical provider calls before retries.

## Outputs

D2-0 must emit:

- arm score distributions;
- source/reproduced/description development-batch learning curves plus final held-out calibration score;
- descriptive P0/P1/P2 pair differences only;
- paired-difference variances/SDs for later power work;
- sampling characterization;
- exact logical/physical call accounting and retry reasons;
- exact overlap counts;
- Artifact export audits;
- frozen output/report hashes.

No p-value, confirmatory PASS/FAIL classification, SESOI, non-inferiority margin, or final confirmatory N is authorized by this calibration lock.

## Interpretation rule

After D2-0 completes, the development-only record is inspected for the qualitative conditions already stated in `CALIBRATION_PLAN.md`: nontrivial source development, no ceiling saturation, a potentially powerable reproduced-versus-description contrast, estimable pair variation, reliable structured output, and exact export-boundary enforcement.

If the substrate is not viable, it may be revised only as a documented pre-confirmatory development change. D2 confirmatory data must not exist during such revision.
