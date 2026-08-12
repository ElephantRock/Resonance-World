# Phase 3 v2 preregistration — provider-robustness amendment

Status: **LOCKED before any Phase-3 v2 model-backed output was generated or observed**.

Revision: `glm5.2-social-dyads-v2-provider-robustness`

## Why v2 exists

Phase 3 v1 was scientifically locked at World revision `7f6868aa01fdef0a28103ee33a2639a5256c757e` and workflow run `31624267333`. It produced no complete artifact and was never scientifically scored.

The first v1 attempt terminated after Z.AI returned HTTP 429 through all six registered physical attempts. The unchanged rerun terminated when one `intention` response contained only `intention` and omitted required `intended_action`. Because both attempts were incomplete, neither contributes any observation to v2.

## Scientific design is unchanged from v1

The following remain exactly frozen from Phase 3 v1:

- model: `glm-5.2`;
- six joint cases;
- ten agents and five dyads per case;
- all sixty authoritative role assignments and their 20/20/20 action balance;
- decentralized and PIANO arms;
- two-round institutional peer-board protocol;
- four logical model calls per agent;
- controller-broadcast intervention;
- acknowledgement in both arms;
- answer-key blinding and channel information routing;
- 128-token logical-call cap;
- board SHA-256 integrity rule;
- all primary and secondary metrics;
- all exact paired statistical tests;
- all advancement thresholds;
- arm ordering and ascending within-round agent order;
- maximum three concurrent joint cases.

## Provider-only amendment

Field revision: `c16d5ffd8fc8543eff0e401ddcdbca2b6bfb6ecd`.

The v2 Field backend keeps strict local structured-output validation. It changes only what happens after a physical provider attempt fails:

- maximum physical attempts per logical call: **8** instead of 6;
- exponential retry backoff cap: **30 seconds** instead of 8 seconds;
- malformed provider structured output is retryable when the response fails the exact registered stage contract;
- HTTP 429/5xx, socket timeout, and transport failures remain retryable;
- returned model-ID drift remains an immediate hard failure and is never retried as a contract error.

A malformed response is not accepted, repaired, or selectively scored. It is discarded as a failed physical attempt. A logical call exists scientifically only when a fully contract-valid `glm-5.2` response is obtained within the registered retry ceiling. The same rule applies to both experimental arms.

## Bound prior evidence

The same one-agent prerequisites remain bound:

- Phase 2B acknowledgement artifact: `sha256:6fdc5d0ddf1aa693c81801b78aae4f71f4807215d27960d19bbc9d2c0b62a7e2`;
- Phase 2C controller-broadcast artifact: `sha256:f330a4d5153327a3bca37ea9e30ab8fd7eb3f167f0cb474f708ef0e4fc5a698b`.

## Completeness and scoring

As in v1, both arms must contain exactly sixty valid role records and all reconstructed ten-agent boards must match every member's board digest. There are no partial scores, no discretionary exclusions, and no reuse of records from either invalid v1 attempt.

## Advancement gate

Unchanged from v1:

- PIANO-minus-decentralized dyad-failure delta <= `-0.40`;
- agent-role-failure delta <= `-0.40`;
- joint-case-completion delta >= `+0.50`;
- cross-channel-contradiction delta <= `-0.25`;
- outcome-report-mismatch delta <= `+0.05`;
- exact paired sign-test p <= `0.05` for both primary outcomes.

Passing advances to a Phase-4 institutional experiment. Failure is evidence to revise the ten-agent social protocol before adding institutional complexity.
