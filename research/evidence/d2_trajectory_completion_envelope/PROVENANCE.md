# Provenance — D2 trajectory completion envelope

- Issue: `#234`
- Construction PR: `#235` (outcome-bearing apparatus; preserve unmerged)
- Frozen construction candidate: `c3d154131b11ef8f87afe89069cabf10c8dca3a3`
- Sole-child activation commit: `d40e9d16c2b7be5c8af475f47cbaaccc078715cb`
- Workflow: `D2 Trajectory Completion Envelope Qualification`
- Workflow run: `34270324142`, attempt `1`
- Artifact id: `10073647438`
- Artifact name: `d2-trajectory-completion-envelope-result`
- Artifact ZIP digest: `sha256:604c626aed1291d6c27d2a3c044232635d8c87d33015ba4229dd1640edf92d93`
- Exact `RESULT.json` SHA-256: `b0ca9a93cdc2c9568847f94c4524764cfddc66e90c8d02c3ef54889ee2044b9a`
- Guard repair merge: `47383f2b18c993965c89350609a4c9691897bdde` (`#228`)
- Guard git blob: `4b8896235d8048523d007400d0acfe85470f628c`
- Stage-1 evidence merge: `f8ac997112efb1b677691f50029415cc6274f7b2` (`#233`)
- Stage-1 canonical result SHA-256: `9982e3c059e864cc06027173cfc3e3c17de7276393c501b15d4a4831a722f6a5`
- Provider/product: Z.AI / existing GLM Coding Plan
- Requested model: exact `glm-5.3`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- OpenAI SDK: `2.21.0`
- httpx: `0.28.1`

## Outcome summary

- Registered topology: 4 trajectories × 55 = 220 logical calls.
- Attempted: 122; completed: 119.
- Physical provider sends: 125, all observed failure-path sends HTTP 200 and within the 400-send hard ceiling.
- Attribution mismatches: 0.
- Unexpected outbound blocks: 0.
- Budget-cap blocks: 0.
- Provider workers observed: 125; alive after drain: 0; transport hooks restored cleanly.
- `schema_like_2`: PASS 55/55.
- `schema_like_0`: FAIL at logical 38, `developed_160/development12`, after 2 API/model calls and 2 HTTP 200 sends.
- `schema_like_1`: FAIL at logical 73, `developed_80/development6`, after 2 API/model calls and 2 HTTP 200 sends.
- `schema_like_3`: FAIL at logical 173, `developed_40/development5`, after 2 API/model calls and 2 HTTP 200 sends.
- The three failures share bounded error fingerprint `sha256:6c4f4c2c878ac5b6e3b0770ba32dfa183c6e7e1e91b0927b2d8186a5d18047af`, corresponding to the harness classification “Hermes returned non-completed engineering logical call.”
- Qualification: **FAIL** because all four trajectories were required to complete 55/55.

No raw credentials, raw provider bodies, raw error messages, hidden scientific truth, or scientific scores are preserved.
