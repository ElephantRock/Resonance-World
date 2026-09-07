# D2-vNext Hermes / Coding Plan qualification closeout

Issue: #213  
PR: #218

## Authoritative execution

- frozen construction candidate: `1960b612a762758b6e707627fd9f42ddde2bac3c`
- sole-child authorization commit: `c2c2fb20adf0cea5cfd02c5868ee3b093f2341b4`
- workflow: `D2-vNext Hermes Coding Plan Qualification Execution`
- workflow run: `34141991757`
- run attempt: `1`
- operational conclusion: `success`
- artifact id: `10026248168`
- artifact name: `d2-vnext-hermes-coding-plan-qualification-result`
- artifact digest: `sha256:d29a353267c9126f5d364b6fa173e64f9d3be27db7a5b416b04305574f943cad`
- authoritative result-file SHA-256: `2ff850c4a632fc4e381d397e0155db07d1bd78659e014ab3a9e5a1fff839e297`

The exact artifact result is preserved in `CODING_PLAN_HERMES_QUALIFICATION_RESULT.json`.

## Registered decision

`qualification_pass=false`.

The all-three-probe qualification criterion was not met. This is a valid negative engineering qualification outcome and must not be relabeled as a pass.

## Observed execution

Exactly three logical probes ran. The physical-send guard observed exactly three provider HTTP sends total: one per probe. No send was blocked by the per-probe or campaign cap, and no unregistered outbound HTTP request was attempted.

No probe reported terminal HTTP 429 / provider code 1113. The first two probes failed locally with the bounded `RuntimeError` fingerprint for `Hermes returned non-completed result` (`sha256:431764bbe3267f01d73b9427b1fd562297eb8e5d3d2c7f9881886c160431ff84`). The authoritative workflow log records `finish_reason=length` for those responses; under the frozen `max_iterations=1` contract Hermes could not perform its continuation/completion step. The third probe completed successfully with a non-empty final response.

Therefore the observed failure is not another General-API-style balance/entitlement 429 result. The intended Hermes/Coding Plan route demonstrably initiated and received provider responses, but the pre-registered all-probe Hermes completion criterion was not satisfied because the frozen sentinel envelope was too tight for two of the three responses.

## Result ceiling

This stream supports only the following engineering conclusions:

1. the pinned Hermes `zai` route using `GLM_BASE_URL=https://api.z.ai/api/coding/paas/v4` was exercised under the intended Coding Plan credential path;
2. exactly three bounded physical provider sends occurred, with no terminal 429/1113 observation and no guard violation;
3. one of three Hermes probes completed with a non-empty response;
4. all-three-probe qualification was **not established**;
5. effective upstream model identity remained unobserved at the supported product boundary.

This stream does **not** establish D2 capability acquisition, schema generalization, mechanism efficacy, registry eligibility, Acceptance, or a successful GLM-5.3 scientific stratum.

## Lifecycle / governance

The consumed request stream must not be rerun. No replacement probe, workflow rerun, post-outcome threshold change, or rescue execution is authorized in this stream.

A future attempt to clear this dependency must be a **new prospective engineering stream** with a separately frozen completion/output envelope while preserving the intended Coding Plan route. Any provider execution in that successor stream requires a new exact-candidate authorization.

No scientific campaign was executed. No registry or Acceptance action is authorized. Historical Substrate remains **OFF**.
