# H5 execution record

Status: **completed — scientific FAIL** (`historical_substrate_institutional_mediation_failed`).

Prospective fixture lock from the preregistered materializer:

- Plane E SHA-256: `173b3e8a6461c38eb3bad6e3dd7ed6b38807f512b5ff64bfc0ead4f19ed4cbb9`
- Plane K SHA-256: `f59804690f06782133881d648b0bcd1cb94c818a6e2747d8d2754b0a45dddb19`
- fixture manifest SHA-256: `b86ee29bc9fa1c2fee5e7c03abbb8ea13590467e3efc8c675d67756f0f3784dd`
- hosted pre-key request-plan SHA-256: `5fe373d3ec5ee4704ee0f6ccd0a1b5c49676670ee5254a13f8edafcf03e84951`
- organization decision cells: 432
- logical model calls: 1,296
- canonical record budget: 6 per unit/generation
- authority grants: 36 (one execution capability per unit/generation)

The fixture identities were frozen and hosted apparatus-lock run `31763545183` passed before any H5 provider call. An earlier issue comment incorrectly labeled local stub hash `72af88a43ec5b3425a0db1d5583525d65f8f3c625657698838adda77364f1e85` as the hosted request-plan hash; #152 contains the prospective correction preserving the historical comment.

## Incomplete transport attempt 1

Exact candidate `2407594b33655eb9de2b3ae7430af49f09f490cc`, workflow run `31763629650`.

The frozen apparatus lock passed and the live job began. It completed 71 organizational cells before sustained Z.AI HTTP 429 rate limiting caused one request to exhaust the original four transport attempts. No complete 432-cell live-output artifact was written or uploaded and no evaluator executed. Partial stochastic responses were not inspected before the transport repair and are excluded from scientific estimation.

This panel is transport-failed and scientifically unclassifiable, not an H5 PASS or FAIL.

## Transport-only repair

Commit `46a7a2e04a974eba0251ad693053e1efd3a897fc` changed only provider scheduling/retry controls: 2.0-second global request-start spacing, concurrency 2, up to 12 transient transport/format attempts, and long HTTP-429 backoff. Apparatus-only run `31764417716` reproduced the frozen fixture hashes and hosted pre-key request-plan hash before the classifiable campaign.

No fixture byte, scientific prompt, analyst partition, model identifier, sampling temperature, output cap, role/protocol semantic, canonical evidence, authority state, evaluator rule, test, gate, or threshold changed.

## Classifiable campaign

Exact candidate `7afa2d139049b1fdb80de2a95d76b49430b6a046`, workflow run `31764482769`.

- apparatus-lock: success
- live-provider-panel: success
- 432/432 organizational cells completed
- 1,296 logical model calls
- 1,378 physical provider attempts
- evaluator plane absent from live inference: success
- frozen live-output content SHA-256: `c0448e5eaa6fdca199832ff8262f34e8e027643582967034088f8f8bf42ac5b5`
- live artifact `9207100866`, digest `sha256:cdde1924dbb88707eefcc6e856470c7467f699014422ba50b298d03caf979504`

Frozen-output evaluator job `94668378810` evaluated the same provider artifact twice. `result.json`, `manifest.json`, `audit.json`, and evaluator exit status were byte-identical across the two runs. The evaluation step itself succeeded; the final workflow enforcement step exited 3 because the scientific classification was the registered FAIL rather than PASS.

Authoritative hashes:

- result: `c4d40f7df4a7f82d324e1cfa81c9a2d90a147a72f87b75e4bcee62a3c3d06029`
- manifest: `b93d518adb70aef890cc8720af5804cbd1e1328a4e85f9905b21be39cfc9a8cb`
- audit: `d6d757ff6459cf6b52d3c0f362b80b802fc21ea2b4f31b6a83de585263f25265`
- evaluation artifact `9207107658`, digest `sha256:898c01eb9a4ab9f1b3a8c2309d27006aad5b2c7a6f5be55ad89b00a58531cd9d`

The authoritative classification is `historical_substrate_institutional_mediation_failed`. Failed gates are 10, 12, and 13. All other gates pass. The record is immutable; no confirmatory retuning or rerun is permitted. Production/default Historical Substrate remains OFF.
