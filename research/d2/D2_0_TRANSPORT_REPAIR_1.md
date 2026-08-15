# D2-0 transport repair 1

Status: **prospective development-only transport amendment after incomplete v0.1 calibration run; no D2-0 scientific result existed at amendment time**.

## Trigger

D2-0 workflow `31889041385`, job `95022443875`, failed during an in-flight `reproduced/evaluation` request. The v0.1 request contract asked the provider for 24 actions plus private strategy in one strict two-key JSON object.

The failing logical call exhausted 8 schema/format retries with only:

```text
action_count
action_count
output_keys
action_count
output_keys
output_keys
output_keys
action_count
```

The workflow stopped before structural verification or artifact upload. One pair had completed internally before the failing call, but no campaign output/report was emitted or retained as a scientific calibration record. No D2 confirmatory cohort, holdout, or outcome exists.

Issue #167 records this failure prospectively in comment `5302646723`.

## Repair scope

This amendment changes only provider-output robustness and evaluation batching. It does **not** change:

- the 8 frozen D2-0 Field pairs;
- private hidden-policy families, flips, or action permutations;
- source/destination development examples or their seed namespaces;
- objective feedback content;
- the Capability Artifact export boundary;
- model line (`glm-5-turbo`) or development temperature (`0.8`);
- the sampling-characterization temperature panel;
- any scientific contrast based on observed outcomes;
- the absence of confirmatory data;
- production/default Historical Substrate OFF.

## Amended evaluation transport

The 24 held-out calibration cases are split deterministically into **three chunks of 8** for every arm.

For `source_developed`, `reproduced`, and `description_only`:

- development remains two calls × 8 cases;
- evaluation becomes three calls × 8 cases;
- the first evaluation chunk receives the second development batch's local history (outcome-bearing for source/reproduced, unlabeled for description-only);
- later evaluation chunks receive no evaluation outcomes and no new labeled history;
- private strategy may be carried between evaluation chunks, but no correctness signal from evaluation is ever returned.

For `fresh`:

- evaluation is also three calls × 8 cases;
- it receives no development history or outcome feedback;
- it may carry only its own unlabeled working strategy between held-out chunks, preserving the same non-outcome-bearing evaluation-context opportunity available to other arms.

Thus the amended per-pair logical-call accounting is:

```text
source_developed = 5
reproduced       = 5
description_only = 5
fresh            = 3
--------------------
per pair         = 18
8 pairs          = 144
sampling panel   = 18
TOTAL            = 162 logical calls before retries
```

## Amended JSON contract

`actions` remains mandatory and must have the exact chunk length with only the four registered action tokens.

`strategy` becomes optional. If it is absent, the previous private strategy is carried forward unchanged. If present, it must be a bounded string. Harmless additional JSON keys are ignored rather than treated as scientific failures. No unrecognized field is used to score or update treatment state.

This is a transport parser amendment, not a scientific treatment amendment.

## Outcome discipline

The failed v0.1 attempt is preserved as an incomplete development transport record. Repair 1 will execute from a new marker and workflow candidate. Its output, if structurally complete, remains development-only evidence for deciding whether a later D2 confirmatory preregistration is warranted.

No p-value, SESOI, non-inferiority margin, confirmatory N, D2 S-classification, or registry promotion is authorized by this repair.
