# C3R — feedback-based source acquisition construction protocol

Status: **unfrozen / credential-free construction / NO SCIENTIFIC INFERENCE**.

This document supplements PROBE_PROTOCOL.md. The original c3r_g2_probe module deliberately tests a source with scripted exhaustive observations; it remains unchanged as a fixture. This new apparatus tests a narrow prerequisite: can an explicit feedback learner acquire a better same-context action policy from grades that arrive after its own choices, then supply its observed episodes to the existing G2 compiler?

## Run

    python -m resonance_world.c3r_g1_acquisition

The command prints a canonical JSON diagnostic. It performs no network or provider-model request, no persistence or registry mutation, and no live authorization.

## What is different from the old scripted source

- Each source controller has a persistent per-context attempts/successes state.
- The controller chooses its next executable plan **before** its action is evaluated.
- The local grader sees public task operands and a private, fixed context-to-plan rule.
- Only a Boolean post-action success bit is sent back to update the exact pending decision. Incorrect-context, duplicate and premature feedback is rejected.
- Two source controllers per context are prospectively counterbalanced to begin with opposite initial plans, **independent of the hidden rule**. Each must examine both available plans at least twice before exploitation.
- A fresh comparator has the same controller type, identity and assigned starting plan but no observed feedback.
- Source qualification uses different operand instances from source training and G2 destination tasks; public-payload collisions are rejected in addition to ID collisions.
- The G2 compiler is now fed the records of *actual attempted actions in the deterministic fixture*, not a manually scripted list of two-arm success labels.
- A/C/B/D/D_MINUS downstream comparisons reuse the same admitted source records and grader-blind controllers from c3r_g2_probe.py. Raw C and compiled D intentionally compute the same sufficient statistic.

## Interpretive boundary

This is **algorithmic action-policy adaptation from observed feedback in a tiny deterministic task**. It is not LLM/agent cognitive learning, multi-schema transfer, institution formation, or causal organizational uplift. The hidden task rule is constructed by the fixture, the source agent policy is a few lines of deterministic code, and the model is never invoked.

The learner and the grader live in the same local program and are separated by function contracts, not a security boundary. Hashes bind self-generated fixture records but do not authenticate an external evaluator. Qualifying on unfamiliar operands within the same hidden context rule is not generalization to a new schema.

There is one organization-level development unit in this probe, regardless of task count. No power calculation, cluster-aware inferential CI, preregistered SESOI or independently replicated population exists yet.

## Required negative and integrity controls

1. No feedback -> policy remains the fresh baseline; no fictional acquisition.
2. Unmatched feedback, duplicated feedback, wrong plan, or non-Boolean grades -> error.
3. Opposite hidden mappings must lead to opposite acquired decisions **without changing learner code**.
4. Novice initial plans must be exactly balanced per context. This corrects an early construction defect where incidental identity hashes made all default novices wrong. This correction preceded any frozen experiment and is not a posthoc rescue of a scientific result.
5. Heldout public operands must not duplicate training or each other, even when identifiers differ.
6. Source learned policy, raw-history policy and compiled policy are independently inspectable, but neither may consult the grader before making a decision.
7. C and D remain equivalent on the fixture. Any downstream G2 effect estimate is strictly descriptive and is not evidence that compiling a policy is causally superior to raw-history reasoning.
8. Feedback and compilation compute costs are visible at a coarse operation level; they are not calibrated token/compute-equivalent treatments.

## Next scientific decision (not authorized here)

A prospective G1 study needs unknown task-generation rules, calibrated baseline competence and true model-mediated source behavior, independent evaluator-owned evidence, explicit treatment allocation, realistic acquisition protocol, and fresh cohort evaluation. Only after G1 acquisition is supported should a different G2 organizational mechanism be designed and frozen with fair raw-history/role controls. A full succession or regeneration experiment remains a separate gated study.

The experiment remains under PR #310 as **construction only**; successful CI may validate the apparatus but cannot promote an architecture pattern or mechanism registry node.
