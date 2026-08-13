# H0 — Historical Substrate Activation Safety

## Accepted classification

`historical_substrate_activation_safety_pass`

Accepted exact head: `91ef1c6403adf0062b63e62447ac8683d74101e0`.

H0 establishes only the registered activation-safety claim: under the frozen bounded-access contract and fixtures, historical evidence can be exposed to an organizational controller through an explicit audited decision path without future/private leakage, authority substitution, direct World/Field history reads, or disabled-arm interference.

## Retained scientific history

The first candidate at `6dbe0e5589861cdbb5358db198c24e2066f29a66` is retained but not accepted. Its internal evaluator classified PASS and its exact-head reproductions were byte-identical, but exact-head review found two P1 contract mismatches: authority verification was fixture-local rather than a canonical World-owned primitive, and the direct-edge runtime sentinels were declarative rather than actual forbidden-consumer calls.

Amendment #134 was recorded before the corrected authoritative rerun. The correction did not change the frozen H0 Plane E, Plane K, meta roots, query identities, cutoffs, bounds, sentinels, or Gates 0–8. It narrowly extracted the Phase4C opaque-attestation `AuthorityLedger` into World production code and added a default-off pure Historical Substrate consumer guard. Runtime forbidden consumers now fail closed with `HistoricalAccessForbidden`.

The authority primitive is provenance-bound to validated Phase4C World revision `b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1` and workflow `31638087507`.

## Frozen apparatus

Preregistered base: `039657c198f9c1bc5158031f579d74a40717828f`.

Frozen roots:

- Plane E: `e7e6d21689fe75b9674bee483d4ec055f1985536b545e6ef73d0f6cb809855c7`
- Plane K: `f1b1058dd2ad32d88a377b44869d1dda4e76d427e2d31f848d5bcaa338966d8c`
- Meta: `b80ee7569b4f310ac440b853936162ed99405b0c17dd6779857d27a81dd7c188`

Pre-outcome apparatus workflow run: `31735984391`.

## Accepted execution

Dedicated H0 workflow run: `31738779781`.

Both isolated exact-head reproductions succeeded and the downstream authoritative-file byte comparator succeeded. Standing CI, ContextGraph integration, W4-00, W4A, W4A.1, and apparatus-lock checks were green at the accepted head.

Authoritative artifacts:

- primary: artifact `9196190014`, ZIP digest `sha256:8a6bf2cdf0b927603c60f67a91abfc2e171757a5d039fdfd5774652674a88a1a`;
- independent: artifact `9196192942`, ZIP digest `sha256:b1b4dc24b7024679b898f5dabac693c64f62b5ec056a60a2264d3d067653a1c1`.

Archive digests differ because ZIP metadata are outside the scientific contract; the extracted authoritative products were byte-compared successfully by the workflow.

Registered diagnostics:

- four bounded historical queries evaluated exactly;
- eight pre-cutoff ContextGraph claims present in participant-facing/researcher-safe output from nine total stored fixture claims;
- future sentinel excluded;
- private Field sentinel excluded;
- conflicting evidence preserved without truth collapse;
- historical authority evidence rejected by current World authority verification;
- all four forbidden runtime history-consumer routes rejected by the Historical Substrate guard;
- access-disabled no-retrieval trajectory byte-identical to observer-only;
- pre-key bytes unchanged after Plane K restoration;
- Gates 0–8 all `true`.

Authoritative result SHA-256: `917560b62700d384e62aa4867c4e4719a783e4e7a4e8cd7c5ffd359ef8d602be`.

## Boundary retained

Production/default Historical Substrate remains disabled. H0 does not establish performance benefit from history, superiority of structured ContextGraph history over an informationally equivalent flat log, sustainability improvement, generational accumulation, or persistent institutional intelligence.

The next H-series question is H1: whether historical access has causal value, with no-history, informationally equivalent flat-history, and structured ContextGraph-history arms preregistered before execution.
