# D2 JSON-skeleton conformance evidence

This directory preserves the exact outcome of issue #273 / construction PR #274.

The registered result is **FAIL_STRUCTURED_CONTRACT** under the frozen engineering rule (`qualification_pass=false`, `apparatus_failure=false`). The sole authorized run attempted all 72 fresh probes and produced 71 effective completions: 66 native Hermes completions plus 5 valid terminal-iteration overrides. The unchanged exact parser accepted 71/72 responses and rejected one clean non-empty response: logical index 7 (`skeleton_fresh_evaluation_07`, seed 4,400,008) with `json_decode_failure`. JSON-mode compatibility failures and placeholder leaks were both zero. The run observed 78 physical provider sends with clean transport/accounting, worker drain, and hook restoration.

The exact 88,379-byte `RESULT.json` from GitHub Actions artifact `10422765947` is preserved losslessly as deterministic gzip bytes whose exact 12,652-character base64 encoding is split across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part07`. Parts 01-06 each contain 1,888 base64 characters plus a terminating newline; part 07 contains 1,324 base64 characters plus a terminating newline. Reconstruct the exact result from this directory with:

```sh
cat RESULT.json.gz.b64.part{01..07} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The recovered file must have SHA-256 `89d69113727aafad6bc470df63306f43470cd65172d98d63e20899a1a149c04f`. The deterministic gzip bytes have SHA-256 `711ca863eb39e481b2aec229a61b8f9048a90846de100c5c9db6fcb13525f4a3`, and the original artifact ZIP digest is `sha256:b6aa3e9ee443e3a4fa68c4df76f82409e5278ddf1ebb32e36d569fdd95708b67`. `RESULT.sha256` records all three digests.

The request stream is consumed and must not be rerun, cycled, replaced, or rescued in place. This evidence is engineering-only and does not authorize scientific scoring/source acquisition, Acceptance/registry action, Historical Substrate activation, deployment/publication, billing/purchase, credential, or permission changes. The preserved #270, #263, and #258 `FAIL_STRUCTURED_CONTRACT` outcomes and #251 `PASS` remain unchanged.
