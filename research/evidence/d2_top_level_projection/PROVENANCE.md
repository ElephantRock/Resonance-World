# D2 top-level projection structured-completion conformance — provenance

## Execution identity

- Issue: #263
- Construction PR: #266
- Frozen candidate: `d17ca2e15915e222605ec47c0afdd1ed05107080`
- Sole-child activation: `62f7c0b295882d99a9dabc8c74f4054628cf5642`
- Workflow: `D2 Top-Level Projection Qualification`
- Workflow run: `34789327898`, attempt 1
- Artifact ID: `10328290005`
- Artifact ZIP digest: `sha256:274b850954c167397646fa86b8baf9e505f47159984475550482fc6644405997`
- Exact `RESULT.json` size: 99,064 bytes
- Exact `RESULT.json` SHA-256: `03944abb3ac19ec57b5cca743d797bf06c99e09d37f0c5f3461192153983a6a3`
- Lossless evidence encoding: deterministic gzip (`mtime=0`), encoded to 15,104 base64 characters and split exactly across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part08`
- Deterministic gzip SHA-256: `c9dcad9b1162f0f0ceb6ccdfff9d0b155f24ce14079b0326ea2b079b8c802030`

Each base64 part contains exactly 1,888 payload characters plus one terminating newline. The exact result can be reconstructed with:

```sh
cat RESULT.json.gz.b64.part{01..08} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The reconstructed `RESULT.json` SHA-256 must match the value above. `RESULT.sha256` records the result, gzip, and original artifact ZIP digests.

### Evidence-packaging repair

Evidence PR #267 initially preserved the result with a single `RESULT.json.gz.b64` file, but a post-merge Codex review correctly found that the stored base64 payload contained one extra character and therefore could not be decoded losslessly. PR #268 repairs only that packaging defect by replacing the malformed single-file representation with the eight exact multipart base64 segments described above. The source artifact, authoritative result bytes, checksums, qualification classification, and all execution facts are unchanged. No provider call, rerun, rescue, replacement, or reinterpretation occurs in this repair.

## Frozen substrate

- Provider: Z.AI GLM Coding Plan
- Provider/API mode/model: `zai` / `chat_completions` / `glm-5.3`
- Request intervention: `response_format={"type":"json_object"}`
- Parser intervention: `ignore_unknown_top_level_keys_only`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- Hermes `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- Provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`
- Qualified terminal-adapter blob: `ba16d2eb4b7255437c8ab224e91d5ed093897990`
- Top-level projection adapter blob: `84ee0c1624f35ff0b8c68aad3721e48d134dea9e`
- Fresh request namespace: `rw.d2-top-level-projection.v1`
- Registered probes: 72 independent fresh D2-shaped engineering probes

## Authoritative outcome

`FAIL_STRUCTURED_CONTRACT` under the registered engineering rule; `qualification_pass=false`; `apparatus_failure=false`.

The sole authorized run attempted all 72 probes and produced 53 effective completions: 45 native Hermes completions and 8 valid terminal-iteration overrides. It observed 82 physical provider sends. Transport/accounting remained clean: zero unexpected-outbound blocks, zero provider-cap blocks, zero attribution-mismatch blocks, zero provider workers alive after drain, and transport hooks restored after drain. JSON-mode compatibility failures were zero.

The exact parser reported 18 non-empty invalid responses, and the bounded projection parser also reported 18 non-empty invalid responses. The projection path was exercised by 16 probes and ignored exactly one unknown top-level key on each of those probes, for 16 ignored unknown keys total. Every projection-used probe remained invalid because `actions` was not a list. Thus the registered adapter path was exercised but did not make the required structured contract reliable.

Across all 72 probes, bounded parse diagnostics were: 53 `exact_valid`, 16 `actions_not_list`, 2 `json_decode_failure`, and 1 `wrong_action_count`. The 18 non-empty responses that remained invalid after projection were logical indices 1, 5, 6, 14, 16, 17, 19, 21, 30, 39, 41, 45, 48, 49, 50, 56, 69, and 71. Of those, 16 were `actions_not_list`, logical 19 was `wrong_action_count`, and logical 39 was a non-empty `json_decode_failure`.

Logical index 24 (`projection_developed_development_06`, `developed_development`, budget 80, seed 4200024) made two clean attributed HTTP-200 provider sends but had an empty final response. It therefore recorded `json_decode_failure`, adapter reason `final_response_empty`, and did not count in the 18 non-empty projected-parse-invalid responses.

The repeated unknown-key fingerprint observed on the 16 projection-used probes is retained only as the bounded diagnostic already present in the exact result evidence; this provenance does not attempt to reverse or reveal the raw unknown key name.

Because clean non-empty responses remained invalid after the registered unknown-key-only projection, the registered outcome is `FAIL_STRUCTURED_CONTRACT`. This is not a JSON-mode compatibility failure and not an apparatus failure. The preserved #258 result remains `FAIL_STRUCTURED_CONTRACT`, #255 remains `FAIL`, and #251 remains `PASS`; none is rerun, rescued, replaced, or reinterpreted.

## Authority ceiling

This is engineering-only completion evidence. It performs no scientific scoring or source acquisition and creates no Acceptance-plane decision, Mechanism Registry promotion, Historical Substrate activation, deployment, publication, billing/purchase, credential, or permission authority. Same-stream rerun, marker cycling, replacement, or in-place rescue is prohibited after this outcome-bearing execution.
