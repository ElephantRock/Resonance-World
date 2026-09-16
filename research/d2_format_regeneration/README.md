# D2 bounded format-regeneration engineering qualification

This directory materializes issue #276 as an engineering-only fresh conformance stream. It asks whether one tightly gated format-regeneration agent invocation can recover an otherwise clean non-empty response rejected by the unchanged exact D2 parser.

The primary prompt semantics and provider/runtime substrate remain those of #273. A retry is allowed only after a clean first exact-parser failure and receives only the bounded diagnostic class plus the original fresh probe. Raw first-response content is not included in the retry prompt or persisted. Valid first responses are never retried; empty, transport-unclean, compatibility-rejected, or otherwise ambiguous first attempts are not retried.

The stream contains 72 fresh probes under `rw.d2-format-regeneration-retry.v1`, seeds 4,500,001–4,500,072. The transport envelope remains 36 physical sends per logical probe and 180 total, with exact attribution and worker-drain/hook-restoration fail-closed checks.

Marker-absent candidate construction and zero-provider review are autonomous. The provider path is one-shot only after exact-head review. This stream is engineering-only and creates no scientific, Acceptance, Historical Substrate, deployment, billing, credential, or permission authority.
