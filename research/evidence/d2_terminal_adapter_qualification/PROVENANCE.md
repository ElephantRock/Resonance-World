# D2 terminal adapter qualification — integrity-failure provenance

This directory preserves the authoritative outcome of issue #246 / PR #247 without rerunning or reinterpreting the consumed request stream.

## Frozen execution identity

- Frozen candidate: `e3aa97da750352ad12be202b457db88217cbe16f`
- Sole-child activation: `50cf8ed1ade2cef456ed9715a16fdccfd90932c3`
- Workflow: `D2 Terminal Adapter Qualification`
- Workflow run: `34561367646`, attempt 1
- Frozen provider/model route: Z.AI coding-plan `chat_completions`, model `glm-5.3`
- Registered probe count: 72
- Registered campaign ceiling: 180 physical provider sends
- Authorization basis: Autonomous Operating Charter Amendment A1 standing execution authority

The activation commit was exactly one commit ahead of the frozen candidate and added only `research/d2_terminal_adapter/RUN_D2_TERMINAL_ADAPTER_QUALIFICATION`.

## Authoritative outcome

**INTEGRITY / APPARATUS FAILURE BEFORE PROVIDER EXECUTION.**

The `authorization-integrity` job failed while evaluating the durable one-use history command because the runner GitHub CLI rejected combining `gh api --paginate --slurp` with `--jq`:

`the --slurp option is not supported with --jq or --template`

The failure occurred before the credentialed execution job. `execute-bounded-adapter-qualification` was skipped, so the #246 stream made zero provider/model sends and produced no result artifact. The adapter itself was therefore **not evaluated** by this run; this record must not be interpreted as either an adapter PASS or adapter FAIL.

## Preservation and claim boundary

The run is preserved as attempt 1 and is not rerun, marker-cycled, or rescued in place. Issue #236 remains an apparatus failure, and the preserved issue #243 terminal-response observation remains `VALID_TERMINAL_RESPONSE_OBSERVED`; neither predecessor is rewritten by #246.

No scientific scoring or source-acquisition evidence was generated. No Acceptance-plane decision, Mechanism Registry promotion, production Historical Substrate activation, deployment, publication, credential change, billing change, or purchase is authorized or performed by this preservation record. The claim ceiling is **engineering terminal-adapter qualification only**.

`RESULT.json` is the bounded machine-readable preservation record for this outcome.
