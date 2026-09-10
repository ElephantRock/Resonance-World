# D2 terminal-response observability — preserved outcome

Issue: #243
Construction PR: #244
Diagnostic outcome: **VALID_TERMINAL_RESPONSE_OBSERVED**

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

Structural workflow success means only that the bounded evidence path completed. The authoritative diagnostic is the exact result JSON preserved beside this file.

## Registered observation

All 72 fresh non-scientific probes completed the bounded apparatus without an apparatus failure. The observed distribution was:

- 64 probes completed in one Hermes API/model call and one HTTP-200 physical send;
- 8 probes reached exactly two Hermes API/model calls and exactly two clean HTTP-200 physical sends;
- all 72 produced non-empty, parse-valid structured responses;
- all 8 two-call probes had `hermes_completed=false` while `failed=false`, `partial=false`, `interrupted=false`, and no Hermes error was present;
- all 8 satisfied the prospectively frozen exact-two-clean-send disambiguation rule, excluding retry/grace/summary-send contamination;
- therefore `valid_terminal_response_count=8` and the diagnostic outcome is `VALID_TERMINAL_RESPONSE_OBSERVED`.

Transport/accounting remained clean: 80 physical provider sends total, 0 unexpected-outbound blocks, 0 provider-budget blocks, 0 logical-attribution mismatch blocks, 80 provider worker threads observed, 0 alive after drain, and transport hooks restored.

This establishes only that, under the frozen realistic D2-shaped engineering envelope, valid non-empty structured responses can exist at Hermes' second-call terminal boundary while Hermes reports `completed=false`. It does not accept or override those terminal responses and does not establish any scientific mechanism result.

## Governance boundary

This outcome does not rerun, rescue, replace, or reinterpret #223, #229, #231, #234, or #237. In particular, #234 and #237 remain authoritative FAIL outcomes under their own frozen apparatuses.

Same-stream rerun or tuning of #243 is prohibited after this outcome-bearing execution. No scientific scoring, source acquisition, Acceptance/registry action, D2e action, Historical Substrate activation, deployment, publication, billing change, credential change, permission change, or destructive evidence action is authorized by this record. Production/default Historical Substrate remains OFF.
