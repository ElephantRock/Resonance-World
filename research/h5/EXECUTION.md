# H5 execution record

Status: **transport repair after incomplete first provider attempt; no scientific classification yet**.

Prospective fixture lock from the preregistered materializer:

- Plane E SHA-256: `173b3e8a6461c38eb3bad6e3dd7ed6b38807f512b5ff64bfc0ead4f19ed4cbb9`
- Plane K SHA-256: `f59804690f06782133881d648b0bcd1cb94c818a6e2747d8d2754b0a45dddb19`
- fixture manifest SHA-256: `b86ee29bc9fa1c2fee5e7c03abbb8ea13590467e3efc8c675d67756f0f3784dd`
- hosted pre-key request-plan SHA-256: `5fe373d3ec5ee4704ee0f6ccd0a1b5c49676670ee5254a13f8edafcf03e84951`
- organization decision cells: 432
- logical model calls: 1,296
- canonical record budget: 6 per unit/generation
- authority grants: 36 (one execution capability per unit/generation)

The fixture identities were frozen and hosted apparatus-lock run `31763545183` passed before any H5 provider call. An earlier issue comment incorrectly labeled local stub hash `72af88a43ec5b3425a0db1d5583525d65f8f3c625657698838adda77364f1e85` as the hosted request-plan hash; the issue record contains a prospective correction preserving the historical comment.

## Incomplete transport attempt 1

Exact candidate `2407594b33655eb9de2b3ae7430af49f09f490cc`, workflow run `31763629650`.

The frozen apparatus lock passed and the live job began. It completed 71 organizational cells before sustained Z.AI HTTP 429 rate limiting caused one request to exhaust the original four transport attempts. No complete 432-cell live-output artifact was written or uploaded and no evaluator executed. Progress logs exposed no model-selected action/evaluator outcome. Partial stochastic responses have not been inspected and are excluded from scientific estimation.

This incomplete panel is therefore transport-failed and **scientifically unclassifiable**, not an H5 PASS or FAIL.

## Transport-only repair

The next candidate changes only provider scheduling/retry controls in `scripts/run_h5_institutional.py`:

- global physical-request start interval: 2.0 seconds;
- cell worker concurrency: 2;
- maximum transient transport/format attempts: 12;
- HTTP 429 backoff: exponential from 30 seconds, capped at 120 seconds, honoring `Retry-After` up to the same cap.

The repair does not change fixture bytes, scientific prompts, analyst partitions, model identifier, sampling temperature, output cap, role/protocol semantics, canonical evidence, authority state, evaluator logic, statistical tests, gates, or thresholds. A fresh hosted apparatus lock must reproduce the same fixture hashes and the same `5fe373...` pre-key request-plan hash before a new classifiable live campaign is triggered.
