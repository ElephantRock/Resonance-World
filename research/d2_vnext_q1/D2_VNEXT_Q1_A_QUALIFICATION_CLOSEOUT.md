# D2-vNext-Q1-A qualification closeout

**Status:** consumed / frozen A1 result  
**Tracking:** #290  
**Successor construction:** #293  
**Authoritative workflow:** `35998227643`, attempt 1  
**Frozen marker-absent candidate:** `4f1ce13c3136ceeb0b0bb478ecad44ac21db9d26`  
**Sole-child authorization commit:** `8efdc1ada39165606312744bd590cb3fe016416b`

## Frozen classification

The authoritative Q1-A classification is:

`D2-vNext-Q1-A1 — minimum_screen_completion_failure`

The workflow completed operationally, all four mixed-schema provider shards were loaded, transport/accounting integrity passed, and terminal-failure observability was complete. The prospective screen nevertheless failed because every registered schema was below the frozen `>=12/16` complete evaluator-analyzable-pair continuation floor.

| schema | attempted | complete/analyzable | failed | completion rate |
|---|---:|---:|---:|---:|
| `threshold_at_4` | 16 | 7 | 9 | 43.75% |
| `parity_pair` | 16 | 10 | 6 | 62.50% |
| `interval_pair` | 16 | 8 | 8 | 50.00% |
| `pairwise_order` | 16 | 0 | 16 | 0.00% |
| **total** | **64** | **25** | **39** | **39.06%** |

The run observed **2,078** physical provider sends under the explicitly authorized **4,608** campaign ceiling.

## Evidence identities

Canonical provider output:

- artifact ID: `10809296804`
- artifact ZIP digest: `sha256:aff8e4896feda874b682c959c8ca4455f8fb167799ccc22842340aa09a0094be`
- exact provider-output SHA-256: `12d25e5c158ccc7e9c76a4f35e44cc2a9ccc8c4930854ab65172b0b3788b0075`

Frozen evaluation:

- artifact ID: `10809451841`
- artifact ZIP digest: `sha256:cbf29c3b997490137f83be4ee85ad9cbf3eeb8bcd8b17e1da5549853b482c957`
- exact evaluation-result SHA-256: `cba92dd2a8e75ca5a98cfe90a3eb8180a7eea44ff34ead29dc69020a5a229b4a`

Provider shard outputs reproduce the hashes preserved by the canonical aggregate:

| shard | artifact ID | artifact ZIP digest | exact shard-output SHA-256 |
|---:|---:|---|---|
| 0 | `10808741778` | `sha256:3e75e236ecfd89ac025a1545a59375e722f08956255a8e256ebd15f3d1c2a213` | `ce472ccb3fdcb2cb94c23a4de457acd8ea2f57e00a68a0f937e8a5b7787eccb9` |
| 1 | `10809213417` | `sha256:daa75ff199e87c626c5bfc442c8b3c7bab6548cbebd8d274e2184400f5d3b02a` | `6f006280caa357727bb8f79469e3b58ab4971297564a1cd2ef3c2abe0d570552` |
| 2 | `10808449855` | `sha256:a3cbd40b968d5501ff8fd7c882a2dbb55e65af0c1993a0c90a7a66b97aeb58a7` | `a32d46d1f36e90bc7780d499a4397c52b13e09ba9ec4f3f8b4b0fd2395a9eada` |
| 3 | `10810270133` | `sha256:cabd846b86ce943c1dfeee3e5e122462aa94975a2419e8a7c8973c726d069844` | `7384cdbcc4d3699fdebcd6e31147f80331d16741e16cf7b138e12f668e1ecc99` |

The deterministic Q1-A cohort commitment remains:

`21ae386da6fdba2883a331864fcaffc51f9fa8adb58aa43ee9d68519cadc3686`

## Failure fingerprint

All 39 failed pairs terminate under the same registered bounded failure identity:

- `failure_class=q1_logical_call_no_accepted_exact_completion`
- `error_type=RuntimeError`
- `error_sha256=dcc7d4db0f10a0bcb4427479e08e3b2f529ad93c090e1a624397484831c53960`

Registered fingerprint preimage:

`RuntimeError:D2-vNext-Q1 logical call has no accepted exact completion`

The detailed bounded terminal-failure distribution is preserved separately in `diagnostics/D2_VNEXT_Q1_A_FAILURE_FORENSICS.{json,md}`.

## Governance closeout

Q1-A is consumed and must not be rerun, rescued, replenished, or marker-cycled. The frozen A1 result makes the Q1-A continuation gate false, so **Q1-B provider execution is not authorized** under the frozen Q1 contract.

This closeout does not authorize scientific-effect gates, Acceptance, Mechanism Registry promotion, D2e execution, deployment/publication, credential or permission changes, or Historical Substrate activation.

Future mechanism work is a fresh revision tracked by #293 and requires its own construction, freeze, exact-candidate review, and separate provider-execution authorization.
