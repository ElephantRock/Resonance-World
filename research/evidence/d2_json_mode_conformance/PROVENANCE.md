# D2 JSON-mode structured-completion conformance — provenance

## Execution identity

- Issue: #258
- Apparatus PR: #261
- Frozen candidate: `6dd5e81fafe26a8a9d10bed8dcf5e6ccd708dc32`
- Sole-child activation: `b79bafbddd376829f4efb071e83237863c194299`
- Workflow: `D2 JSON Mode Conformance Qualification`
- Workflow run: `34707347243`, attempt 1
- Artifact ID: `10302561413`
- Artifact ZIP digest: `sha256:6df950cb8e8762f429ffb6f1e1d640725d2f98fde31609c58271590d7e0e9c53`
- Exact `RESULT.json` SHA-256: `3a41456e11de292300c97ac55ac8c33e9093b8cdf09e760affd5954e653a5294`

## Frozen substrate

- Provider: Z.AI GLM Coding Plan
- Provider/API mode/model: `zai` / `chat_completions` / `glm-5.3`
- Request intervention: `response_format={"type":"json_object"}`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- Hermes `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- Provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`
- GitHub authorization helper blob: `4fec4f0bfac06ae17a87a7c148dea6521736a97a`
- Qualified terminal-adapter blob: `ba16d2eb4b7255437c8ab224e91d5ed093897990`
- Fresh request namespace: `rw.d2-json-mode-conformance.v1`
- Registered probes: 72 independent fresh D2-shaped engineering probes

## Authoritative outcome

`FAIL_STRUCTURED_CONTRACT` under the registered engineering rule; `apparatus_failure=false`.

The sole authorized run attempted all 72 probes and produced 70 effective completions: 66 native Hermes completions and 4 valid terminal-iteration overrides. It observed 76 physical provider sends. Transport/accounting remained clean: zero unexpected-outbound blocks, zero provider-cap blocks, zero attribution-mismatch blocks, zero provider workers alive after drain, and transport hooks restored after drain. JSON-mode compatibility failures were zero.

Two native Hermes completions failed the unchanged exact parser despite clean one-send HTTP-200 transport:
- logical index 24, `jsonmode_developed_development_06`, `developed_development`, budget 80, seed 4000024; bounded parse diagnostic `extra_keys`; final-response SHA-256 `f561a666270c4786aa0a9515c7a1ec8d2dbcde27b7084833c6604f393b923480`.
- logical index 52, `jsonmode_developed_evaluation_16`, `developed_evaluation`, budget 160, seed 4000052; bounded parse diagnostic `extra_keys`; final-response SHA-256 `a0eb4d73d44051b371e644231af0c32fd74ef10ee74e7b555ddabd21c3736424`.

Thus the registered JSON-mode request was provider-compatible, but it did not make the unchanged exact eight-action parser reliable at 72/72. The predecessor #255 trajectory result remains `FAIL` and #251 remains `PASS`; neither is rerun, rescued, or reinterpreted.

## Authority ceiling

This is engineering-only completion evidence. It performs no scientific scoring or source acquisition and creates no Acceptance-plane decision, Mechanism Registry promotion, Historical Substrate activation, deployment, publication, billing/purchase, credential, or permission authority. Same-stream rerun or replacement is prohibited.
