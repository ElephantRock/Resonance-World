# D2 terminal adapter v2 qualification — provenance

## Execution identity

- Issue: #251
- Apparatus PR: #253
- Frozen candidate: `65f80d7f66bda043a581c30494175c6361fa8e4f`
- Sole-child activation: `bfc3defaa9a008735183b502fd147f6db16cec73`
- Workflow: `D2 Terminal Adapter V2 Qualification`
- Workflow run: `34578268112`, attempt 1
- Artifact ID: `10190577392`
- Artifact ZIP digest: `sha256:d50aa105c89f5faf9bbfe7b3456553b1a3d17e62832967e02fd846124cbbf870`
- Exact `RESULT.json` SHA-256: `f0c9ba663642bfec83b04287b71991ec3da275e9c231a3666acf88c3ce5b956e`

## Frozen substrate

- Provider: Z.AI GLM Coding Plan
- Provider/API mode/model: `zai` / `chat_completions` / `glm-5.3`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- Hermes `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- Provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`
- GitHub authorization helper blob: `4fec4f0bfac06ae17a87a7c148dea6521736a97a`
- Authorization-gate repair merge: `09d6c5c6ac7884213b492da62a1c236f08f1d62c`
- Fresh request namespace: `rw.d2-terminal-adapter.v2`
- Fresh seeds: `2000000..2000071`

## Authoritative outcome

`PASS` under the registered engineering rule. All 72 fresh probes were effective completions: 71 native Hermes completions and 1 terminal-iteration override. The override was logical index 36 (`adapter_v2_b80_36`, seed 2000036, budget 80), with exactly two Hermes API calls and two attributed HTTP-200 physical sends, a non-empty parse-valid structured response, and no Hermes failure/partial/interrupted/error flags.

Transport/accounting remained clean: 73 total physical sends; zero unexpected-outbound, provider-cap, and attribution-mismatch blocks; zero provider workers alive after drain; transport hooks restored after drain.

Preserved #243 causal evidence remained unchanged and its credential-free regression reproduced 72 effective completions = 64 native + 8 terminal overrides. Preserved #246 remains `INTEGRITY_APPARATUS_FAILURE_PRE_PROVIDER` with zero provider/model traffic and is not reinterpreted.

## Authority ceiling

This is engineering-only terminal structured-completion qualification evidence. It performs no scientific scoring or source acquisition and creates no Acceptance-plane decision, Mechanism Registry promotion, Historical Substrate activation, deployment, publication, billing/purchase, credential, or permission authority. Same-stream rerun or replacement is prohibited.
