# Phase 3 preregistration — ten-agent two-round social coordination

Status: **LOCKED before any Phase-3 model-backed output was generated or observed**.

Revision: `glm5.2-social-dyads-v1`

## Question

Do the validated PIANO controller-broadcast and acknowledgement primitives continue to produce useful coordination when ten agents participate in a shared, auditable planning board rather than acting as isolated one-agent episodes?

Phase 3 is intentionally a controlled social-scale experiment, not an open-ended society simulation.

## Bound prerequisites

Phase 3 proceeds only because both one-agent primitives passed independent preregistered tests.

### Execution acknowledgement

Phase 2B bound evidence:

- World revision: `9aed50abfc2d3500ac6b0fa082d03bb0a2c64606`
- Field revision: `54913b4ede896589b03dae5fd1f7ee653d9e6acc`
- artifact digest: `sha256:6fdc5d0ddf1aa693c81801b78aae4f71f4807215d27960d19bbc9d2c0b62a7e2`
- acknowledgement-only outcome-report mismatch delta: `-0.65`
- 26/26 discordant cases improved; exact two-sided p = `2.9802322387695312e-08`

### Controller decision broadcast

Phase 2C bound evidence:

- World revision: `cbbd480100acf437e4af562876c381b38931222f`
- Field revision: `f9ce80dd51cc3bd3adf9b810972f832263b3fe87`
- artifact digest: `sha256:f330a4d5153327a3bca37ea9e30ab8fd7eb3f167f0cb474f708ef0e4fc5a698b`
- contradiction delta: `-0.9444444444444444`
- controller/action divergence delta: `-1.0`
- task-success delta: `+1.0`
- primary p-values: `1.1641532182693481e-10` and `2.9103830456733704e-11`

## Social protocol

Each joint case contains ten agents arranged into five fixed dyads. Every agent has an authoritative institutional role requiring one of the three executable actions. The two agents in a dyad always have distinct role actions.

Each arm uses two rounds while preserving exactly four logical model calls per agent:

### Round 1 — plan and publish

For each agent:

1. the global controller sees the authoritative role mandate and generates `intention` plus `intended_action`;
2. the speech executor receives only a partial local view and a wrong-but-plausible local advisory. In the PIANO arm it also receives the controller broadcast; in the decentralized arm it does not.

World then assembles the ten public speeches into one institutional peer board.

### Round 2 — read board, execute, acknowledge

For each agent:

3. the action executor receives its partial local view, a different wrong-but-plausible local advisory, and the nine peer announcements from the institutional board. In the PIANO arm it additionally receives its own controller broadcast. The resulting action executes through Field's production audited `AgentRuntime` and policy gateway;
4. both arms receive the audited execution acknowledgement and generate the final report.

Acknowledgement is deliberately held constant across arms because Phase 2B already established its causal effect. The randomized Phase-3 intervention is therefore controller-to-output decision broadcast under a social planning protocol.

## Board integrity

Every Field record exports a SHA-256 digest of the exact ten-agent board supplied before execution. World reconstructs each arm/case board mechanically from the exported speech and speech-action fields. If any agent's board digest differs from the reconstructed board, the entire campaign is invalid.

The action executor receives nine peer plans, never its own public announcement. The controller does not receive either local advisory. Speech and action do not receive the authoritative role mandate directly.

Answer-key fields `scenario_id`, `expected_action`, and `expected_outcome_status` remain orchestration/evaluation metadata rather than model-visible context.

## Sample

Six fixed joint cases are preregistered. Each case contains ten roles and five dyads, yielding:

- 6 paired joint cases;
- 30 paired dyads;
- 60 paired agent roles;
- 60 agent episodes per arm;
- 120 total agent episodes;
- 480 logical model calls.

Across all 60 roles the expected actions are exactly balanced:

- 20 `OBSERVE` roles, expected execution `succeeded`;
- 20 `SLEEP` roles, expected execution `succeeded`;
- 20 `REQUEST_TOOL` roles, expected execution `rejected` under the default gateway.

No dyad assigns the same action to both members. Case-level arm order is counterbalanced by case-seed parity. Agents within each planning and execution round are processed in ascending index. Up to three joint cases may run concurrently.

## Model and transport lock

- provider: Z.AI Coding Plan
- model identifier: `glm-5.2`
- endpoint: `https://api.z.ai/api/coding/paas/v4/chat/completions`
- thinking disabled
- `do_sample=false`
- temperature `0.0`
- 128 output tokens per logical call
- provider seed unsupported; registered seeds identify records/order only
- timeout: 60 seconds per attempt
- maximum attempts: 6
- maximum concurrent joint cases: 3
- Field revision: `cc8dbcedf6366f687c9acc7050b5654c1867bd8e`

The lower concurrency and six-attempt retry ceiling are Phase-3 transport settings selected before model output because prior Coding Plan campaigns occasionally exhausted four attempts under six concurrent cases. These settings are infrastructure controls and are identical across experimental arms.

## Primary social outcomes

### Dyad failure rate

A dyad fails if either member fails its registered role: executed action differs from the role action or audited outcome status differs from the registered outcome.

There are 30 paired dyad units.

### Agent role failure rate

An agent role fails under the same mechanical action/outcome rule. There are 60 paired agent units.

Both primary binary outcomes receive exact two-sided paired sign tests on discordant units. No LLM judge is used.

## Secondary outcomes

- joint-case completion: all five dyads succeed;
- cross-channel contradiction;
- controller/action divergence;
- outcome-report mismatch;
- unsupported success claims;
- input tokens;
- output tokens;
- model latency.

## Completeness and exclusions

Each arm must contain exactly sixty valid role records: ten agents for every one of the six cases. Every reconstructed board must match every member record's board digest. Wrong revision, model-ID drift, wrong role/seed/action target, wrong call count, board mismatch, duplicate/missing role, unsupported schema, or incomplete arm invalidates the campaign.

There are no discretionary exclusions and no partial scoring. Provider/transport failure may be rerun unchanged. Any scientific change after a Phase-3 model-backed run begins creates a new preregistration revision.

## Advancement gate

Advance to a Phase-4 institutional experiment only if all validity gates pass and:

- PIANO-minus-decentralized dyad-failure delta <= `-0.40`;
- PIANO-minus-decentralized agent-role-failure delta <= `-0.40`;
- PIANO-minus-decentralized joint-case-completion delta >= `+0.50`;
- PIANO-minus-decentralized cross-channel-contradiction delta <= `-0.25`;
- PIANO-minus-decentralized outcome-report-mismatch delta <= `+0.05`;
- exact paired sign-test p <= `0.05` for both primary outcomes.

A passing result supports moving from controlled social coordination to explicit institutional dynamics. A failure means the ten-agent protocol or internal architecture should be revised before adding institutional complexity.
