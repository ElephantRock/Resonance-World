# D2 bounded format-regeneration structured-completion conformance — provenance

## Execution identity

- Issue: #276
- Construction PR: #277
- Frozen marker-absent candidate: `a4ae72e842564456df47f64c6d59292e51482c92`
- Sole-child activation: `ebe29d2fcac5bd1bdde0f96622e0834442fcec76`
- Exact-head operator review: PR review `5217395552`, `Autonomous-Operator-Exact-Head-Review: PASS`
- Codex review: unavailable because the repository's Codex review usage limit was reached; no Codex review result is claimed
- Workflow: `D2 Format Regeneration Qualification`
- Workflow run: `35041981399`, run number 1, attempt 1, event `push`
- Authorization-integrity job: `104623608282`, success
- Execution job: `104623635027`, success
- Artifact ID: `10425866286`
- Artifact name: `d2-format-regeneration-result`
- Artifact size: 11,877 bytes
- Artifact ZIP digest: `sha256:a8eadf8ee3fc754843b0a02b87b8dad73c2b330aa2459b7fe7a4fd8c4debf1f6`
- Exact `RESULT.json` size: 166,294 bytes
- Exact `RESULT.json` SHA-256: `88d0b7d3a19aa0f75c99308743ad2964710a9321e4159008670d9b1785c9bc9f`
- Lossless evidence encoding: deterministic gzip (`mtime=0`), encoded to 15,408 base64 characters and split across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part09`
- Deterministic gzip SHA-256: `c79929a16a642ca3027a4685e9661ccbb542b18fbc5ca9ff1826d8e3fdf2aa6c`

Parts 01-08 each contain exactly 1,888 payload characters plus one terminating newline. Part 09 contains exactly 304 payload characters plus one terminating newline. The exact result can be reconstructed with:

```sh
cat RESULT.json.gz.b64.part{01..09} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The reconstructed `RESULT.json` SHA-256 must match the value above. `RESULT.sha256` records the result, deterministic gzip, and original artifact ZIP digests.

## Frozen substrate

- Provider: Z.AI GLM Coding Plan
- Endpoint: `https://api.z.ai/api/coding/paas/v4`
- Provider/API mode/model: `zai` / `chat_completions` / `glm-5.3`
- Request intervention: `response_format={"type":"json_object"}`
- Primary prompt intervention: unchanged #273 non-copyable positional JSON skeleton and final self-check
- Primary system-prompt SHA-256: `92ba97ccc1e5aec273114785d0d8a5c533ba46a6340d7c74f9fc085efe516c6e`
- Retry intervention: exactly one fresh Hermes format-regeneration invocation only after a clean, non-empty, exactly attributed first response is rejected by the unchanged exact parser
- Retry input restriction: original fresh probe plus bounded parser diagnostic class only; raw first-response content is not propagated
- Parser intervention: `none_unchanged_exact_eight_action_contract`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- Hermes `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- Hermes `pyproject.toml` blob: `95a1dfddd74bc399dd7f23f8d0143852b5689463`
- OpenAI SDK: `2.21.0`
- httpx: `0.28.1`
- Provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`
- Qualified terminal-adapter blob: `ba16d2eb4b7255437c8ab224e91d5ed093897990`
- GitHub authorization queries blob: `4fec4f0bfac06ae17a87a7c148dea6521736a97a`
- Request-plan blob: `c170288e4f0a250187f35890977f2bc4732f8ca1`
- Probe-manifest blob: `0c2f4aca3d5aecdd7428374aa5ec60804a2b1d4f`
- Fresh request namespace: `rw.d2-format-regeneration-retry.v1`
- Fresh seeds: 4,500,001 through 4,500,072
- Registered probes: 72 independent fresh D2-shaped engineering probes: 18 each `fresh_evaluation`, `developed_development`, `developed_evaluation`, and `oracle_evaluation`; developed shapes split six each across budgets 40/80/160
- Max concurrency: 4
- Max agent invocations per probe: 2
- Max iterations per invocation: 2
- Provider-send caps: 36 sends per logical probe, 180 sends total

## Authoritative outcome

`PASS` under the prospectively frozen engineering rule; `qualification_pass=true`; `apparatus_failure=false`.

The sole authorized run attempted and effectively completed all 72 registered probes. It recorded 71 native Hermes completions and one valid terminal-iteration override, with 80 physical provider sends. Transport/accounting remained clean: zero unexpected-outbound blocks, zero provider-cap blocks, zero logical-attribution-mismatch blocks, zero provider workers alive after drain, and transport hooks restored after drain. JSON-mode compatibility failures were zero and bounded placeholder leaks were zero.

The unchanged exact parser accepted 65 first attempts directly. Exactly seven first attempts were clean, non-empty, exactly attributed parser failures, all with diagnostic `extra_keys`; all seven were therefore eligible for the single bounded retry, all seven retries were exact-valid, and no third invocation occurred:

- logical 24, `regeneration_developed_development_06`, `developed_development`, budget 80, seed 4,500,025: first 171 bytes / `extra_keys`; retry 179 bytes / `exact_valid`; 2 sends.
- logical 25, `regeneration_developed_development_07`, `developed_development`, budget 80, seed 4,500,026: first 270 bytes / `extra_keys`; retry 181 bytes / `exact_valid`; 2 sends.
- logical 27, `regeneration_developed_development_09`, `developed_development`, budget 80, seed 4,500,028: first 236 bytes / `extra_keys`; retry 73 bytes / `exact_valid`; 2 sends.
- logical 28, `regeneration_developed_development_10`, `developed_development`, budget 80, seed 4,500,029: first 288 bytes / `extra_keys`; retry 236 bytes / `exact_valid`; 2 sends.
- logical 47, `regeneration_developed_evaluation_11`, `developed_evaluation`, budget 80, seed 4,500,048: first 196 bytes / `extra_keys`; retry 73 bytes / `exact_valid`; 2 sends.
- logical 49, `regeneration_developed_evaluation_13`, `developed_evaluation`, budget 160, seed 4,500,050: first 181 bytes / `extra_keys`; retry 73 bytes / `exact_valid`; 2 sends.
- logical 50, `regeneration_developed_evaluation_14`, `developed_evaluation`, budget 160, seed 4,500,051: first 255 bytes / `extra_keys`; retry 73 bytes / `exact_valid`; 2 sends.

The terminal exact structured-parse invalid count was zero, retry-used count was seven, retry-success count was seven, and every terminal accepted result was exact-valid. The retry payload did not include raw first-response content. The run persisted no raw credentials, raw provider response bodies, raw provider error bodies/messages, or raw final-response content. Hermes native `completed` was not mutated.

The predecessor #273, #270, #263/#264, and #258 outcomes remain unchanged, and #251 remains the qualified terminal-adapter PASS; no predecessor stream was rerun, rescued, replaced, widened, or reinterpreted.

## Authority ceiling

This is engineering-only completion evidence. `PASS` here qualifies the prospectively frozen bounded format-regeneration engineering mechanism under its registered contract; it is not a scientific result and creates no scientific-score, source-acquisition, Acceptance-plane, Mechanism Registry promotion, Historical Substrate activation, deployment, publication, billing/purchase, credential, or permission authority. Same-stream rerun, marker cycling, replacement, or in-place rescue is prohibited after this outcome-bearing execution.
