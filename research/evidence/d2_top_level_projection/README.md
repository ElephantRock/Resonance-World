# D2 top-level projection conformance evidence

This directory preserves the exact outcome of issue #263 / construction PR #266.

The registered result is **FAIL_STRUCTURED_CONTRACT** under the frozen engineering rule (`apparatus_failure=false`). The sole authorized run attempted all 72 probes and produced 53 effective completions: 45 native Hermes completions plus 8 valid terminal-iteration overrides. The bounded top-level projection path was exercised on 16 probes, but all 16 remained invalid after projection because the required `actions` field was not a list. Across non-empty final responses, 18 probes remained invalid after projection. JSON-mode compatibility failures were zero.

The exact 99,064-byte `RESULT.json` from GitHub Actions artifact `10328290005` is preserved losslessly as deterministic gzip bytes whose exact 15,104-character base64 encoding is split across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part08`. Each part contains 1,888 base64 characters plus a terminating newline. Reconstruct the exact result from this directory with:

```sh
cat RESULT.json.gz.b64.part{01..08} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The recovered file must have SHA-256 `03944abb3ac19ec57b5cca743d797bf06c99e09d37f0c5f3461192153983a6a3`. The deterministic gzip bytes have SHA-256 `c9dcad9b1162f0f0ceb6ccdfff9d0b155f24ce14079b0326ea2b079b8c802030`, and the original artifact ZIP digest is `sha256:274b850954c167397646fa86b8baf9e505f47159984475550482fc6644405997`. `RESULT.sha256` records all three digests.

PR #268 repairs only the evidence packaging after the single-file base64 payload merged by #267 was found to contain multiple character-level corruptions. Relative to the exact encoding, repair required two character substitutions and removal of one spurious character. It does not rerun, replace, rescue, or reinterpret the qualification result.

The request stream is consumed and must not be rerun, cycled, replaced, or rescued in place. This evidence is engineering-only and does not authorize scientific scoring/source acquisition, Acceptance/registry action, Historical Substrate activation, deployment/publication, billing/purchase, or credential/permission changes. The preserved #258 `FAIL_STRUCTURED_CONTRACT`, #255 `FAIL`, and #251 `PASS` remain unchanged.
