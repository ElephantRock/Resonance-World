# D2 terminal-response observability — preserved outcome

Issue: #243
Construction PR: #244
Registered outcome: **VALID_TERMINAL_RESPONSE_OBSERVED**

## Authoritative execution

- frozen candidate: `1bad60067309ee4f14334bb393026db2d0548757`
- sole-child activation commit: `933c91aaf9b24ee67513d27b8b2323dd9ba6e720`
- workflow: `D2 Terminal Response Observability Qualification`
- workflow run: `34378693252`
- run attempt: `1`
- artifact: `d2-terminal-response-observability-result`
- artifact ID: `10115044240`
- artifact ZIP digest: `sha256:4abd3201f43ee5208ee1d5a836ae1249af585fd96d479a8d79440fe123ef8678`
- exact `RESULT.json` SHA-256: `cde58890d2d6bd1027381ffa559b385f11883c15e08860a823a1a5017495a9d6`

The workflow completed its bounded evidence path successfully. Structural workflow success is distinct from the registered diagnostic outcome.

## Registered decision

The diagnostic observed the prospectively defined terminal-response phenomenon.

Across 72 fresh non-scientific probes under the frozen realistic D2-shaped envelope:

- 64 probes completed normally after one Hermes API/model call and one HTTP-200 physical send;
- 8 probes reached exactly two Hermes API/model calls and returned `hermes_completed=false`;
- all 8 of those two-call probes nevertheless produced non-empty, parse-valid structured terminal content;
- every valid terminal observation had exactly two clean HTTP-200 physical sends, excluding retry, post-budget grace, or summary-send contamination;
- valid observations by development shape were budget 40 = 4, budget 80 = 2, budget 160 = 2;
- all 72 responses were non-empty and parse-valid.

Transport and worker accounting remained clean:

- 80 physical provider sends total;
- 0 logical-attribution mismatch blocks;
- 0 unexpected outbound HTTP blocks;
- 0 provider-send budget blocks;
- 80 provider worker threads observed;
- 0 provider worker threads alive after drain;
- transport hooks restored after worker drain.

No probe carried a Hermes failure, partial, interrupted, error, or runtime-exception state. Therefore the registered narrow engineering conclusion is supported: under this exact frozen envelope, pinned Hermes can return valid terminal response content on its second iteration while reporting `completed=false`.

## Claim ceiling

This outcome does not accept or override a terminal response and does not establish scientific performance, source acquisition, mechanism validity, or trajectory success. It does not rerun, rescue, replace, or reinterpret #234 or #237; both remain authoritative FAIL outcomes under their own frozen apparatus.

Same-stream rerun or tuning of #243 is prohibited after this outcome-bearing execution. No scientific scoring, Acceptance/registry action, D2e action, Historical Substrate activation, deployment, publication, billing change, credential change, permission change, or destructive evidence action is authorized by this record. Production/default Historical Substrate remains OFF.
