# D2-vNext-Q2 clean-terminal-empty regeneration qualification

**Status:** construction-only / provider execution not authorized  
**Tracking:** #293

Q2 is a fresh mechanism-qualification stream after consumed Q1-A run `35998227643` returned `D2-vNext-Q1-A1`. It does not continue or rescue Q1. Its sole mechanism change is prospective: the existing single independent format-regeneration opportunity remains available for clean nonempty parser-invalid results and is additionally permitted after a strictly clean terminal empty result. The primary request, exact parser, model route, prompts, max iterations, and maximum of two agent invocations per logical call remain frozen.

The clean-empty trigger is fail-closed: the first invocation must have no runtime or Hermes error state, valid completion flag with `completed=false`, zero final-response length, terminal adapter reason `final_response_empty`, exactly clean/attributed transport, no compatibility/budget/attribution defect, and exactly two agent API calls (the frozen iteration bound). No raw first-response content is retained or supplied to the regeneration prompt.

Q2-A uses 16 fresh pairs/schema in four mixed-schema shards. Continuation requires integrity plus at least 12/16 complete evaluator-analyzable pairs for every schema. Q2-A data are not pooled into Q2-B. Q2-B is an independent 96-pair/schema validation, separately authorized only after Q2-A passes unchanged. It preserves the Q1 joint-clearance, exact lower-bound, resource-feasibility, and independent exchangeability-review rules.

The frozen physical-send topology remains 36 sends/logical call and 1,152/shard because Q2 does not increase the maximum agent-invocation count. Credential-free tests must prove this before freeze.

Construction creates no execution marker. Q2-A and Q2-B provider execution are separate explicit exact-candidate authorization boundaries. No scientific-effect claim, Acceptance, registry promotion, D2e, deployment/publication, or Historical Substrate action is authorized.
