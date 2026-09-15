# D2 canonical-JSON prompt structured-completion conformance — provenance

## Execution identity

- Issue: #270
- Construction PR: #271
- Frozen candidate: `ba4765520dc0bff05b3c93091d43c2f471733b48`
- Sole-child activation: `c7161eee4146422bea15c954269cbecc07f86b7b`
- Workflow: `D2 Canonical JSON Prompt Qualification`
- Workflow run: `35027725679`, run number 1, attempt 1, event `push`
- Artifact ID: `10420261445`
- Artifact ZIP digest: `sha256:fa6c484f156334b00b388aacc6124a0ac06c7d0ef78b8b13fccd7bca7326f59e`
- Exact `RESULT.json` size: 90,319 bytes
- Exact `RESULT.json` SHA-256: `ad12207e6a8b7b71be38bd0445d58d298f6f34f07e721de49e9e2972b9f83a6f`
- Lossless evidence encoding: deterministic gzip (`mtime=0`), encoded to 14,692 base64 characters and split across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part08`
- Deterministic gzip SHA-256: `cdde12cb8dafae554389f404b4e808475ef7c0fda2d3ee5a74d2e9d27258ad17`

Parts 01-07 each contain exactly 1,888 payload characters plus one terminating newline. Part 08 contains exactly 1,476 payload characters plus one terminating newline. The exact result can be reconstructed with:

```sh
cat RESULT.json.gz.b64.part{01..08} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The reconstructed `RESULT.json` SHA-256 must match the value above. `RESULT.sha256` records the result, gzip, and original artifact ZIP digests.

## Frozen substrate

- Provider: Z.AI GLM Coding Plan
- Endpoint: `https://api.z.ai/api/coding/paas/v4`
- Provider/API mode/model: `zai` / `chat_completions` / `glm-5.3`
- Request intervention: `response_format={"type":"json_object"}`
- Prompt intervention: `canonical_json_exemplar_and_explicit_array_positional_constraints`
- Parser intervention: `none_unchanged_exact_eight_action_contract`
- Canonical-copy rule: exact-valid response actions equal to the registered exemplar are recorded by bounded `canonical_exemplar_copy`; any copy disqualifies `PASS`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- Hermes `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- Pinned Hermes `pyproject.toml` blob: `95a1dfddd74bc399dd7f23f8d0143852b5689463`, independently required to declare `version = "0.8.0"` before runtime metadata materialization
- Provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`
- Qualified terminal-adapter blob: `ba16d2eb4b7255437c8ab224e91d5ed093897990`
- Fresh request namespace: `rw.d2-canonical-json-prompt.v1`
- Fresh seeds: 4,300,001 through 4,300,072
- Registered probes: 72 independent fresh D2-shaped engineering probes: 18 each `fresh_evaluation`, `developed_development`, `developed_evaluation`, and `oracle_evaluation`; developed shapes split six each across budgets 40/80/160

## Authoritative outcome

`FAIL_STRUCTURED_CONTRACT` under the prospectively frozen engineering rule; `qualification_pass=false`; `apparatus_failure=false`.

The sole authorized run attempted all 72 probes and produced 70 effective completions: 61 native Hermes completions and 9 valid terminal-iteration overrides. It observed 82 physical provider sends: 62 probes used one send and 10 probes used two. Transport/accounting remained clean: zero unexpected-outbound blocks, zero provider-cap blocks, zero attribution-mismatch blocks, zero provider workers alive after drain, and transport hooks restored after drain. JSON-mode compatibility failures were zero.

The unchanged exact parser accepted 70 probes and rejected exactly two:

- logical index 39, `canonical_developed_evaluation_03`, shape `developed_evaluation`, budget 40, seed 4,300,040: non-empty 195-byte final response, diagnostic `extra_keys`, clean single attributed provider send, Hermes native completion true;
- logical index 61, `canonical_oracle_evaluation_07`, shape `oracle_evaluation`, seed 4,300,062: non-empty 74-byte final response, diagnostic `json_decode_failure`, two clean attributed provider sends, Hermes native completion false.

Both invalid probes remained transport-clean and were classified by the unchanged parser as `structured_parse_invalid`. Therefore exact structured completion was not 72/72 reliable and the registered outcome is `FAIL_STRUCTURED_CONTRACT`.

Separately, 16 of the 70 exact-valid responses reproduced the canonical exemplar action sequence and therefore set `canonical_exemplar_copy=true`. The copies occurred on 8 `fresh_evaluation`, 2 `developed_development`, 1 `developed_evaluation`, and 5 `oracle_evaluation` probes. The prospectively frozen outcome precedence is `APPARATUS_FAILURE` > `FAIL_JSON_MODE_COMPATIBILITY` > `FAIL_STRUCTURED_CONTRACT` > `FAIL_PROMPT_CONTRACT` > `FAIL_COMPLETION` > `PASS`. Because two clean responses failed the unchanged exact parser, `FAIL_STRUCTURED_CONTRACT` takes precedence; the 16 copy violations do not change or rescue that classification.

The run persisted no raw credentials, raw provider response bodies, raw provider error bodies/messages, or raw final-response content. Hermes native `completed` was not mutated. Scientific scoring was not performed, Acceptance action was not authorized, production Historical Substrate remained off, and same-stream rerun is explicitly prohibited.

The preserved #263 and #258 results remain `FAIL_STRUCTURED_CONTRACT`, #255 remains `FAIL`, and #251 remains `PASS`; none is rerun, rescued, replaced, or reinterpreted.

## Authority ceiling

This is engineering-only completion evidence. It performs no scientific scoring or source acquisition and creates no Acceptance-plane decision, Mechanism Registry promotion, Historical Substrate activation, deployment, publication, billing/purchase, credential, or permission authority. Same-stream rerun, marker cycling, replacement, or in-place rescue is prohibited after this outcome-bearing execution.
