# D2 bounded format-regeneration conformance evidence

This directory preserves the exact outcome of issue #276 / construction PR #277.

The registered engineering result is **PASS** under the prospectively frozen rule (`qualification_pass=true`, `apparatus_failure=false`). The sole authorized run attempted and effectively completed all 72 fresh probes. The unchanged exact parser accepted 65 first attempts directly; seven clean first attempts were rejected with `extra_keys`, each became eligible for the single bounded format-regeneration invocation, and all seven retries were accepted by the unchanged exact parser. Terminal exact structured-parse invalid count is therefore zero. JSON-mode compatibility failures and placeholder leaks were both zero.

The run observed 80 physical provider sends, 71 native Hermes completions, and one valid terminal-iteration override. Transport/accounting remained clean: zero unexpected-outbound blocks, zero provider-cap blocks, zero logical-attribution-mismatch blocks, zero provider workers alive after drain, and transport hooks were restored after worker drain.

The exact 166,294-byte `RESULT.json` from GitHub Actions artifact `10425866286` is preserved losslessly as deterministic gzip bytes whose exact 15,408-character base64 encoding is split across `RESULT.json.gz.b64.part01` through `RESULT.json.gz.b64.part09`. Parts 01-08 each contain 1,888 base64 characters plus a terminating newline; part 09 contains 304 base64 characters plus a terminating newline. Reconstruct the exact result from this directory with:

```sh
cat RESULT.json.gz.b64.part{01..09} | tr -d '\n' | base64 -d | gzip -dc > RESULT.json
```

The recovered file must have SHA-256 `88d0b7d3a19aa0f75c99308743ad2964710a9321e4159008670d9b1785c9bc9f`. The deterministic gzip bytes have SHA-256 `c79929a16a642ca3027a4685e9661ccbb542b18fbc5ca9ff1826d8e3fdf2aa6c`, and the original artifact ZIP digest is `sha256:a8eadf8ee3fc754843b0a02b87b8dad73c2b330aa2459b7fe7a4fd8c4debf1f6`. `RESULT.sha256` records all three digests.

The request stream is consumed and must not be rerun, cycled, replaced, or rescued in place. This is engineering-only qualification evidence. It does not perform or authorize scientific scoring/source acquisition, Acceptance or Mechanism Registry action, Historical Substrate activation, deployment/publication, billing/purchase, credential, or permission changes. The preserved predecessor outcomes remain unchanged.
