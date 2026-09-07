# D2 campaign-scale pacing qualification closeout

Status: **completed engineering qualification; no tested pacing profile qualified**.

Issue: #210  
PR: #211

## Frozen provenance

- frozen candidate: `96265c4e24ea161a439e6b70d21a9744ce4f2902`
- sole-child authorization commit: `270c1b987f797a4526feb2f50906abe449eafd0a`
- authoritative workflow: `34076950808`, attempt 1, **SUCCESS**
- same-request-stream rerun: **not performed and not allowed**
- artifact: `10002401448` (`d2-campaign-pacing-qualification-result`)
- artifact digest: `sha256:1b5318a1b0b633d4fc978b09759cbc1ccd2226e82eadc179af2d65e24eff6d0e`
- authoritative result SHA-256: `376ea35ba979b7d6f605f255a1eadb3f5c077fa207b4ab0b35daa616533434bf`

The frozen request body, request plan, qualification runner, and hardened transport remained unchanged during outcome-bearing execution.

## Outcome

All **31/31** bounded no-retry engineering requests returned HTTP **429**. Every request verified exactly one initiated physical HTTPS attempt, redirect rejection, and zero followed redirects.

| profile | calls | HTTP 429 | minimum observed start interval | pass |
| --- | ---: | ---: | ---: | --- |
| `baseline_serial_5s` | 3 | 3 | 5.000110 s | no |
| `serial_2s` | 6 | 6 | 2.000104 s | no |
| `serial_1s` | 6 | 6 | 1.000099 s | no |
| `concurrency2_1s` | 8 | 8 | 1.000102 s | no |
| `concurrency4_035s` | 8 | 8 | 0.350099 s | no |

`recommended_profile = null` and `campaign_pacing_qualified = false` because the conservative 5-second serial baseline itself failed.

The bounded provider metadata was identical across all failures: provider code `1113`, provider-message length `61`, provider-message SHA-256 `5cc4e4c3db9ee90fcf0a103a9424adef73c32b4027496fab5222d310ee0dda8d`, response-body length `99`, and response-body SHA-256 `cb014b3986a19957e76833d9799e8ddb0da36f0445d71f62420a06a930857723`. Raw provider error bodies and messages were not persisted.

## Claim ceiling

This execution establishes only that, under the exact authorized candidate, account/provider context, deterministic engineering request shape, and prospectively fixed profiles, all 31 requests returned HTTP 429—including all three 5-second serial baseline calls. Therefore no tested pacing profile qualified.

It does **not** establish the semantic provider-policy cause of code `1113`, future quota or eligibility, source-capability acquisition efficacy, schema generalization, or any scientific mechanism claim. It is not D2d-S2 replacement evidence and does not support a Mechanism Registry or Acceptance-plane transition.

## Governance and next dependency

- no workflow rerun or failed-call replacement
- no scientific source-acquisition campaign authorized
- no registry promotion or Acceptance-plane action authorized
- production/default Historical Substrate remains **OFF**

The next dependency is a **separate prospective engineering diagnosis of provider/account eligibility, quota, or policy compatibility**. Pacing alone is not a sufficient explanation for the observed failures because the 5-second serial baseline also returned 429. Any future external provider call requires separate exact-candidate authorization.
