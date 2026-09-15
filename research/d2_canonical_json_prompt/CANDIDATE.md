# D2 canonical-JSON prompt qualification candidate

Issue #270 prospectively freezes a future-only prompt intervention after the consumed #263 `FAIL_STRUCTURED_CONTRACT` stream.

The sole causal intervention is the system/output instruction: a literal canonical JSON shape exemplar plus explicit requirements that `actions` be a square-bracket array of exactly eight positional action strings. JSON-mode transport, the #251 terminal-completion adapter, the exact parser, provider/runtime pins, transport accounting, and authority ceiling remain unchanged.

This marker-absent candidate performs no provider execution. Activation requires an exact-head review and a sole-child `RUN_D2_CANONICAL_JSON_PROMPT` marker commit. The resulting workflow may execute at most once; rerun, marker cycling, replacement, and in-place rescue are prohibited.

The request is engineering-only. Scientific D2 execution, Acceptance/registry action, Historical Substrate activation, deployment/publication, billing/purchase, credential, and permission changes remain unauthorized.
