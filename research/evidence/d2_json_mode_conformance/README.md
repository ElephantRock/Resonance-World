# D2 JSON-mode structured-completion conformance evidence

This directory preserves the exact outcome of issue #258 / PR #261.

The registered result is **FAIL_STRUCTURED_CONTRACT** under the frozen engineering rule (`apparatus_failure=false`). The sole authorized run attempted all 72 probes and produced 70 effective completions: 66 native Hermes completions plus 4 valid terminal-iteration overrides. Two clean responses failed the unchanged exact parser, both with bounded diagnostic `extra_keys`. JSON-mode compatibility failures were zero.

`RESULT.json` is copied byte-for-byte from GitHub Actions artifact `10302561413` and has SHA-256 `3a41456e11de292300c97ac55ac8c33e9093b8cdf09e760affd5954e653a5294`. The artifact ZIP digest is `sha256:6df950cb8e8762f429ffb6f1e1d640725d2f98fde31609c58271590d7e0e9c53`.

The request stream is consumed and must not be rerun or replaced in place. This evidence is engineering-only and does not authorize scientific scoring/source acquisition, Acceptance/registry action, Historical Substrate activation, deployment/publication, billing/purchase, or credential/permission changes.
