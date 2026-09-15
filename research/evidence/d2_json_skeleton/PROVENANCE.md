# D2 JSON-skeleton structured-completion conformance — provenance

## Execution identity

- Issue: #273
- Construction PR: #274
- Frozen candidate: `e58cfe05dc6e99d96058a1be9596558e847c067d`
- Sole-child activation: `a31ae2256ba54338c9de2896b81db2443781d0c7`
- Workflow: `D2 JSON Skeleton Qualification`
- Workflow run: `35033480944`, run number 1, attempt 1, event `push`
- Artifact ID: `10422765947`
- Artifact ZIP digest: `sha256:b6aa3e9ee443e3a4fa68c4df76f82409e5278ddf1ebb32e36d569fdd95708b67`
- Exact `RESULT.json` size: 88,379 bytes
- Exact `RESULT.json` SHA-256: `89d69113727aafad6bc470df63306f43470cd65172d98d63e20899a1a149c04f`
- Lossless evidence encoding: deterministic gzip (`mtime=0`), encoded to 12,652 base64 characters and split across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part07`
- Deterministic gzip SHA-256: `711ca863eb39e481b2aec229a61b8f9048a90846de100c5c9db6fcb13525f4a3`

Parts 01-06 each contain exactly 1,888 payload characters plus one terminating newline. Part 07 contains exactly 1,324 payload characters plus one terminating newline. The exact result can be reconstructed with:

```sh
cat RESULT.json.gz.b64.part{01..07} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The reconstructed `RESULT.json` SHA-256 must match the value above. `RESULT.sha256` records the result, gzip, and original artifact ZIP digests.

## Frozen substrate

- Provider: Z.AI GLM Coding Plan
- Endpoint: `https://api.z.ai/api/coding/paas/v4`
- Provider/API mode/model: `zai` / `chat_completions` / `glm-5.3`
- Request intervention: `response_format={"type":"json_object"}`
- Prompt intervention: `non_copyable_positional_json_skeleton_and_final_selfcheck`
- Parser intervention: `none_unchanged_exact_eight_action_contract`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- Hermes `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- Provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`
- Qualified terminal-adapter blob: `ba16d2eb4b7255437c8ab224e91d5ed093897990`
- Fresh request namespace: `rw.d2-json-skeleton-selfcheck.v1`
- Fresh seeds: 4,400,001 through 4,400,072
- Registered probes: 72 independent fresh D2-shaped engineering probes: 18 each `fresh_evaluation`, `developed_development`, `developed_evaluation`, and `oracle_evaluation`; developed shapes split six each across budgets 40/80/160

## Authoritative outcome

`FAIL_STRUCTURED_CONTRACT` under the prospectively frozen engineering rule; `qualification_pass=false`; `apparatus_failure=false`.

The sole authorized run attempted all 72 probes and produced 71 effective completions: 66 native Hermes completions and 5 valid terminal-iteration overrides. It observed 78 physical provider sends. Transport/accounting remained clean: zero unexpected-outbound blocks, zero provider-cap blocks, zero logical-attribution-mismatch blocks, zero provider workers alive after drain, and transport hooks restored after drain. JSON-mode compatibility failures were zero and the bounded placeholder-leak diagnostic count was zero.

The unchanged exact parser accepted 71 probes and rejected exactly one non-empty response:

- logical index 7, `skeleton_fresh_evaluation_07`, shape `fresh_evaluation`, seed 4,400,008: non-empty 146-byte final response, diagnostic `json_decode_failure`, two clean attributed HTTP 200 provider sends, Hermes native completion false, terminal override false, and `effective_completed=false`.

That invalid probe remained transport-clean and was classified by the unchanged parser as `structured_parse_invalid`. Therefore exact structured completion was not 72/72 reliable and the registered outcome is `FAIL_STRUCTURED_CONTRACT`.

The run persisted no raw credentials, raw provider response bodies, raw provider error bodies/messages, or raw final-response content. Hermes native `completed` was not mutated. Scientific scoring was not performed, Acceptance action was not authorized, production Historical Substrate remained off, provider-derived strategy propagation was not performed, and same-stream rerun is explicitly prohibited.

The preserved #270, #263, and #258 outcomes remain `FAIL_STRUCTURED_CONTRACT`, and #251 remains `PASS`; none is rerun, rescued, replaced, or reinterpreted.

## Authority ceiling

This is engineering-only completion evidence. It performs no scientific scoring or source acquisition and creates no Acceptance-plane decision, Mechanism Registry promotion, Historical Substrate activation, deployment, publication, billing/purchase, credential, or permission authority. Same-stream rerun, marker cycling, replacement, or in-place rescue is prohibited after this outcome-bearing execution.
