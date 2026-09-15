# D2 canonical-JSON prompt conformance evidence

This directory preserves the exact outcome of issue #270 / construction PR #271.

The registered result is **FAIL_STRUCTURED_CONTRACT** under the frozen engineering rule (`qualification_pass=false`, `apparatus_failure=false`). The sole authorized run attempted all 72 fresh probes and produced 70 effective completions: 61 native Hermes completions plus 9 valid terminal-iteration overrides. The unchanged exact parser accepted 70/72 responses and rejected two clean responses: logical index 39 (`extra_keys`) and logical index 61 (`json_decode_failure`). JSON-mode compatibility failures were zero.

The prompt-side canonical exemplar did not satisfy the registered no-copy requirement either: 16 exact-valid responses reproduced the canonical exemplar action sequence. Because the prospectively frozen outcome precedence places `FAIL_STRUCTURED_CONTRACT` above `FAIL_PROMPT_CONTRACT`, the authoritative classification remains `FAIL_STRUCTURED_CONTRACT`; the copy count is preserved as an additional bounded prompt-compliance diagnostic, not as a reinterpretation of the outcome.

The exact 90,319-byte `RESULT.json` from GitHub Actions artifact `10420261445` is preserved losslessly as deterministic gzip bytes whose exact 14,692-character base64 encoding is split across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part08`. Parts 01-07 each contain 1,888 base64 characters plus a terminating newline; part 08 contains 1,476 base64 characters plus a terminating newline. Reconstruct the exact result from this directory with:

```sh
cat RESULT.json.gz.b64.part{01..08} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The recovered file must have SHA-256 `ad12207e6a8b7b71be38bd0445d58d298f6f34f07e721de49e9e2972b9f83a6f`. The deterministic gzip bytes have SHA-256 `cdde12cb8dafae554389f404b4e808475ef7c0fda2d3ee5a74d2e9d27258ad17`, and the original artifact ZIP digest is `sha256:fa6c484f156334b00b388aacc6124a0ac06c7d0ef78b8b13fccd7bca7326f59e`. `RESULT.sha256` records all three digests.

The request stream is consumed and must not be rerun, cycled, replaced, or rescued in place. This evidence is engineering-only and does not authorize scientific scoring/source acquisition, Acceptance/registry action, Historical Substrate activation, deployment/publication, billing/purchase, credential, or permission changes. The preserved #263 and #258 `FAIL_STRUCTURED_CONTRACT`, #255 `FAIL`, and #251 `PASS` remain unchanged.
