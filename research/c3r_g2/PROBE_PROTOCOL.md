# C3R G2 local probe — executable design and interpretation

**Status:** construction-only fixture. This experiment is neither a preregistered discovery run nor confirmatory evidence for G1, G2, G3, or G4.

## Execution

With the package installed (or PYTHONPATH=src):

    python -m resonance_world.c3r_g2_probe

The command prints a single canonical JSON report to stdout, with no provider/model calls, credentials, network, writes, or evidence-registry updates. Re-running the same code is byte-identical.

## What the fixture actually does

1. A hidden local oracle maps two opaque context labels to opposite two-step arithmetic orderings.
2. A scripted source probe tests both orderings in each context on distinct public operands and obtains evaluator-graded success/failure observations. **This is NOT proof that agents learned through experience.** It supplies valid-looking *fixture* observations for contract/information-flow tests.
3. The source experiences are bound to evidence digests and assembled into a development index; its SHA lock is computed by the fixture itself, not independently attested.
4. The compiler produces one candidate per context if both alternatives have enough source episodes and no tie. The procedure status remains candidate.
5. The probe constructs fresh holdout task IDs **and checks public-input non-overlap**, then evaluates identical tasks with the same two downstream member identities in each arm.
6. Every arm gets exactly two complete proposed two-step solutions. The submitted answer is always the first proposal, selected by a blind fixed rule; there is no hidden-outcome-aware chooser.
7. The oracle grades only task operands/context and the submitted answer. It does not receive arm name, candidate, organization ID, or history.

This fixture remains transparent and deliberately simple; Python's private oracle map is not a security guarantee. A later scientific study requires a separately owned evaluator and source-manifest lock.

## Arm definitions

| Arm | Input information | Proposing policy | What is tested |
| --- | --- | --- | --- |
| A | Public task only | Independent public-hash proposals | Blind independent-proposal baseline (not best-of-two) |
| B | Public task only | Fixed first ordering, nonlearned roles | Fixed-role policy |
| C | Same admitted development episodes available to the compiler | Computes the full raw-history success rates, same support floors as D | Honest raw-history comparator |
| D | Candidate only, previously compiled from those episodes | Executes the candidate's chosen ordering | Compiled procedural policy |
| D_MINUS | Public task only | Same fixed ordering as B | Procedure removal control |

C and D are deliberately *equivalent* on this simple sufficient statistic. This protects against misrepresenting a mere serialization/compilation choice as a new organizational capability. To claim a genuinely independent organizational benefit later, a prospectively distinct intervention and meaningful information/cost/decision constraints are needed.

## Construction expectations and limitations

- Two scripted source contexts, 16 source episodes in total.
- 24 holdout tasks per context, 48 heldout task instances in the default local fixture.
- Five arms including the ablation, 48 submitted task outcomes each.
- B and D_MINUS use the same fixed rule. C and D use the same learned plan under the available evidence.
- At the fixture's chosen hidden rules, C and D each receive 48/48 successes; B and D_MINUS receive 24/48. These **are programmed fixture properties**, not measurements of AI learning or organizational advantage. There is no claim that D outperforms the competent C comparator.
- A uses a blind selector and its success count is merely a deterministic construction diagnostic.
- 48 tasks are **not 48 independent organizations**; the fixture has one underlying development unit.
- Proposal slots and arithmetic operation counts match, but C must read raw history repeatedly while D compiles once. The report exposes these reads and compilation row counts; token/compute parity is not established.

## Safety and integrity checks

- Identical downstream member IDs across all arms; source agents and destination members do not overlap.
- No oracle or evaluator is accepted as a selector parameter.
- Development episode IDs and task public payloads cannot overlap holdout tasks.
- Candidate compilation abstains when samples lack support or tie.
- Evidence digests are checked, but SHA matching is not evidence provenance authentication.
- No raw hidden evaluator labels are supplied to the procedural controller.
- Descriptive success counts and differences are NOT an inferential hypothesis test or acceptance gate.
- No Historical Substrate activation, World truth changes, provider calls, or automatic promotion.

## Required next step before any scientific run

A new prospective design must demonstrate *source acquisition* on an unfamiliar task, introduce a genuinely distinguishable **organization-level** causal intervention (not just a compile/recompute synonym), and calibrate independent organization N, expected paired discordance, minimum analyzable samples, missingness/yield, effect materiality and cluster-aware confidence intervals. Freeze the evaluator and cohorts only after those requirements, then secure independent authorization for any provider/model execution.

The design worksheet at DESIGN_WORKSHEET.md remains **unfrozen**. Any result obtained from this fixture should be labeled construction-only in every downstream artifact.
