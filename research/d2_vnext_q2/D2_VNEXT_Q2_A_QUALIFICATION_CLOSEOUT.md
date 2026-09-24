# D2-vNext-Q2-A qualification closeout

**Status:** consumed / frozen A1 result  
**Tracking:** #293  
**Successor diagnostic construction:** #296  
**Authoritative workflow:** `36039847576`, attempt 1  
**Frozen marker-absent candidate:** `0a47c7b3e4ec2aedd6af62927fcf1949861d2ae5`  
**Sole-child authorization commit:** `cd12daabbc4826ea9f684687e4ab6a361786e412`

## Frozen classification

The authoritative Q2-A classification is:

`D2-vNext-Q2-A1 — minimum_screen_completion_failure`

The workflow completed operationally, all four mixed-schema provider shards were loaded, transport/accounting integrity passed, and terminal-failure observability was complete. The prospective continuation screen failed because `interval_pair` and `pairwise_order` did not meet the frozen `>=12/16` complete evaluator-analyzable-pair floor.

| schema | attempted | complete/analyzable | failed | completion rate |
|---|---:|---:|---:|---:|
| `threshold_at_4` | 16 | 13 | 3 | 81.25% |
| `parity_pair` | 16 | 14 | 2 | 87.50% |
| `interval_pair` | 16 | 11 | 5 | 68.75% |
| `pairwise_order` | 16 | 1 | 15 | 6.25% |
| **total** | **64** | **39** | **25** | **60.94%** |

The run observed **2,766** physical provider sends under the explicitly authorized **4,608** campaign ceiling.

## Evidence identities

Canonical provider output:

- artifact ID: `10828214001`
- artifact ZIP digest: `sha256:14269d002a76b82778d7c83fde6b984bb0af98736a4503df455bb9c11d4ddb1d`
- exact provider-output SHA-256: `0cb7b6260926a55d852819a651d07b7e1e1efc4e0d894d8796700c09705ef2ae`

Frozen evaluation:

- artifact ID: `10829080786`
- artifact ZIP digest: `sha256:1f4ef01a14b92d528b74812635a03a9ee7cc84ec6e87a12521ff7b5f19c0d531`
- exact evaluation-result SHA-256: `444606dbe402cc3e729accd1c0e00435cf4da758b86ba706340c6adad9cf91b9`

Provider shard outputs reproduce the hashes preserved by the canonical aggregate:

| shard | artifact ID | artifact ZIP digest | exact shard-output SHA-256 |
|---:|---:|---|---|
| 0 | `10828417096` | `sha256:9ba2ab5dbe3c5f16e6b5c1a695c49b5e66c8ca8493e823ee244da21ecc6c3c79` | `ec1811c9b1e2af749e937d995eec459657aa54da14bf81b492faa287053ef2ac` |
| 1 | `10827664287` | `sha256:e2942f8c63ef6b15ab750332147cb5c5c417fb5bf018e980f7decfbc98f4ad9b` | `edd92c4afdee2eccb6e9b521eacd6d93035a5dac1df0706d450e85e7258c37c5` |
| 2 | `10828920548` | `sha256:c031098d13663fb733cc0b4d7ca3ceba1d521c858ce6bae822c59d9301964b16` | `53a3731da3a7eee1328c1c6a7e57e909b90bad0bf2ce6e6757985518ec38c50e` |
| 3 | `10828273513` | `sha256:1eb212ac741d42c1de51bae770b6230de6714c408054a62680ccaead3e1e64d5` | `03ff6629ec3995d6e2ce0696d86ea600088968e12f685ba95906ddf5cebae766` |

The deterministic Q2-A cohort commitment remains:

`74ac69fc045c88e93ea08e86d031dcae23fa179bcba03d2b170526085e00b61b`

## Failure fingerprint

All 25 failed pairs terminate under the same registered bounded failure identity:

- `failure_class=q2_logical_call_no_accepted_exact_completion`
- `error_type=RuntimeError`
- `error_sha256=943129b4f6ef7018fbc6bb6dd3faec6a9ae644b0e6cda1763b4de7816bc127a0`

Registered fingerprint preimage:

`RuntimeError:D2-vNext-Q2 logical call has no accepted exact completion`

The detailed bounded terminal-failure and regeneration distribution is preserved separately in `diagnostics/D2_VNEXT_Q2_A_FAILURE_FORENSICS.{json,md}`.

## Governance closeout

Q2-A is consumed and must not be rerun, rescued, replenished, or marker-cycled. The frozen A1 result makes the Q2-A continuation gate false, so **Q2-B provider execution is not authorized** under the frozen Q2 contract.

This closeout does not authorize scientific-effect gates, Acceptance, Mechanism Registry promotion, D2e execution, deployment/publication, credential or permission changes, or Historical Substrate activation.

Future diagnostic or mechanism work is a fresh revision tracked by #296 and requires its own construction, freeze, exact-candidate review, prospective fresh-cohort/sample plan, explicit send ceiling, and separate provider-execution authorization.
