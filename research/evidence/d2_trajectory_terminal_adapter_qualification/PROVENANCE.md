# D2 trajectory terminal adapter qualification — provenance

## Execution identity

- Issue: #255
- Apparatus PR: #256
- Frozen candidate: `7ff9e471f0e383bd272ae9c37b24a59ab031459e`
- Sole-child activation: `756ff40d18d56ff0da4b728b221b15dd4465a855`
- Workflow: `D2 Trajectory Terminal Adapter Qualification`
- Workflow run: `34678448265`, attempt 1
- Artifact ID: `10293395494`
- Artifact ZIP digest: `sha256:a60511f852d8df3c9f61bf7dc5c4e6308a362878c992da3a9185ce06d91726e2`
- Exact `RESULT.json` SHA-256: `c1581fbd8f7e374610adf965d0718258e5a3fe2b01e4654ae3f4be9d0d2b40be`

## Frozen substrate

- Provider: Z.AI GLM Coding Plan
- Provider/API mode/model: `zai` / `chat_completions` / `glm-5.3`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- Hermes `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- Provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`
- GitHub authorization helper blob: `4fec4f0bfac06ae17a87a7c148dea6521736a97a`
- Qualified terminal-adapter blob: `ba16d2eb4b7255437c8ab224e91d5ed093897990`
- Preserved #251 result SHA-256: `f0c9ba663642bfec83b04287b71991ec3da275e9c231a3666acf88c3ce5b956e`
- Fresh request namespace: `rw.d2-trajectory-terminal-adapter.v1`
- Registered topology: 4 trajectories × 55 logical calls = 220

## Authoritative outcome

`FAIL` under the registered engineering rule; `apparatus_failure=false`.

The sole authorized run attempted 98/220 logical calls and produced 95 effective completions: 93 native Hermes completions and 2 valid terminal-iteration overrides. It observed 101 physical provider sends. Transport/accounting remained clean: zero unexpected-outbound blocks, zero provider-cap blocks, zero attribution-mismatch blocks, zero provider workers alive after drain, and transport hooks restored after drain.

Three trajectories stopped on parse-invalid structured responses:
- `terminal_adapter_trajectory_0` stopped at logical index 1 (`fresh/evaluation2`) after a clean one-call/one-send Hermes completion whose final response was non-empty but failed the exact structured parse.
- `terminal_adapter_trajectory_2` stopped at logical index 114 (`developed_40/development1`) after two clean calls/two sends; Hermes reported `completed=false`, but the final response failed the exact structured parse, so no terminal override was accepted.
- `terminal_adapter_trajectory_3` stopped at logical index 200 (`developed_160/development9`) after a clean one-call/one-send Hermes completion whose final response failed the exact structured parse.

`terminal_adapter_trajectory_1` completed all 55/55 calls. The terminal-override path was exercised twice overall, so this is not `ADAPTER_PATH_NOT_EXERCISED`.

The earlier #234 trajectory result remains `FAIL`, #243 remains `VALID_TERMINAL_RESPONSE_OBSERVED`, and #251 remains `PASS`; none is rerun, rescued, or reinterpreted.

## Authority ceiling

This is engineering-only completion evidence. It performs no scientific scoring or source acquisition and creates no Acceptance-plane decision, Mechanism Registry promotion, Historical Substrate activation, deployment, publication, billing/purchase, credential, or permission authority. Same-stream rerun or replacement is prohibited.
