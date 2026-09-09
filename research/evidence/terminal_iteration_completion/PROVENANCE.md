# Terminal-iteration structured completion — preserved outcome

Issue: #237
Construction PR: #240
Registered outcome: **FAIL**

## Authoritative execution

- frozen candidate: `ad81f140bb5513e6166471a286be7eaed5121e8b`
- sole-child activation commit: `d6b6376e10021d64792c10865aee6ed69d42dc8b`
- workflow: `Terminal Iteration Structured Completion Qualification`
- workflow run: `34307651634`
- run attempt: `1`
- artifact: `terminal-iteration-structured-completion-result`
- artifact ID: `10087233849`
- artifact ZIP digest: `sha256:5b752c1fe089c0f45108da79963bf737428c65720b927dfd400c7a6ee33bb7de`
- exact `RESULT.json` SHA-256: `efa2d3d9c73c631d3579021549912cba6c3de6d5020b6d6135c825a3e72ba137`

The workflow completed its bounded evidence path successfully. That structural workflow success does not imply qualification success.

## Registered decision

The qualification failed its prospectively frozen rule.

All four fresh non-scientific probes reached exactly two Hermes API/model calls and exactly two HTTP-200 physical sends. The transport layer remained clean:

- 8 physical provider sends total;
- 0 logical-attribution mismatch blocks;
- 0 unexpected outbound HTTP blocks;
- 0 provider-send budget blocks.

However, every probe produced an empty final response at the registered terminal boundary:

- `hermes_completed=false`;
- `failed=false`;
- `partial=false`;
- `interrupted=false`;
- no Hermes error present;
- `api_calls=2`;
- `final_response_length=0`;
- `structured_parse_valid=false`;
- adapter reason `final_response_empty`;
- `terminal_iteration_override_used=false`.

Therefore:

- all-four adapter acceptance: **false**;
- at least one two-call probe observed: **true**;
- at least one terminal-iteration override observed: **false**;
- qualification: **FAIL**.

This does not establish that Hermes mislabels a valid terminal response as incomplete. Under this exact frozen probe stream, the terminal boundary produced no final response to accept.

## Review note

An automated P1 review comment arrived after the one-shot activation had already begun and asserted that pinned Hermes omitted `api_calls` from the `run_conversation()` result. That assertion is inconsistent with the pinned source and with the authoritative artifact, which records `api_calls=2` for all four probes. The review thread was resolved as non-applicable; it does not change the registered FAIL.

## Governance boundary

This evidence does not rerun, rescue, replace, or reinterpret #223, #229, #231, or #234. In particular, #234 remains an authoritative FAIL under its own frozen apparatus.

Same-stream rerun or tuning of #237 is prohibited after this outcome-bearing execution. No scientific scoring, source acquisition, Acceptance/registry action, D2e action, Historical Substrate activation, deployment, publication, billing change, credential change, permission change, or destructive evidence action is authorized by this record. Production/default Historical Substrate remains OFF.
