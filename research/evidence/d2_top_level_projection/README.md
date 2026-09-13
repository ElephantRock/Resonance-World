# D2 top-level projection conformance evidence

This directory preserves the exact outcome of issue #263 / construction PR #266.

The registered result is **FAIL_STRUCTURED_CONTRACT** under the frozen engineering rule (`apparatus_failure=false`). The sole authorized run attempted all 72 probes and produced 53 effective completions: 45 native Hermes completions plus 8 valid terminal-iteration overrides. The bounded top-level projection path was exercised on 16 probes, but all 16 remained invalid after projection because the required `actions` field was not a list. Across non-empty final responses, 18 probes remained invalid after projection. JSON-mode compatibility failures were zero.

`RESULT.json` is copied byte-for-byte from GitHub Actions artifact `10328290005` and has SHA-256 `03944abb3ac19ec57b5cca743d797bf06c99e09d37f0c5f3461192153983a6a3`. The artifact ZIP digest is `sha256:274b850954c167397646fa86b8baf9e505f47159984475550482fc6644405997`.

The request stream is consumed and must not be rerun, cycled, replaced, or rescued in place. This evidence is engineering-only and does not authorize scientific scoring/source acquisition, Acceptance/registry action, Historical Substrate activation, deployment/publication, billing/purchase, or credential/permission changes. The preserved #258 `FAIL_STRUCTURED_CONTRACT`, #255 `FAIL`, and #251 `PASS` remain unchanged.
