# Fourth REAL crossed trial — GLM-5.2 attempted uniform no-thinking (2026-10-23)

**Data source:** GitHub Actions [39958785805](https://github.com/ElephantRock/Resonance-World/actions/runs/39958785805), result artifact ID **12503337720** (g1-glm52-uniform-nonthinking-20261023), ZIP SHA256 **33421b54572e0ec0f42b0cb85972e9a11348164dcb4d7daa37104b0a4da5ea1d**, JSON SHA256 **76857df44570cfbe955a9c45ba2beeb8c48997a6bed791cff43a9279fcc77c18**. Run ID: g1-crossed-glm52-nonthinking-20261023-04. Internal-only experimental evidence, not scientific acceptance.

## Observation

Model \`glm-5.2\` was requested with \`thinking.type=disabled\` on Z.AI Coding route, four concurrent requests, and a 512-token generation cap uniformly across the source and all three holdout arms.

| Stage/family | Accepted | Invalid output | Not sent | Prescribed |
| --- | ---: | ---: | ---: | ---: |
| Arithmetic development | 7 | 1 | 0 | 8 |
| Text development | 0 | 8 | 0 | 8 |
| Arithmetic qualification | 9 | 0 | 3 | 12 |
| Text qualification | 0 | 0 | 12 | 12 |
| **Total** | **16** | **9** | **15** | **40** |

**25 physical send reservations**, three arithmetic context triplets eligible, no text context complete. In the three valid arithmetic triplets Learned 3/3, Fresh 3/3 and Neutral 2/3. No learned-over-fresh benefit was observed for this separate model/configuration, and the small n prohibits a confirmatory inference.

All eight text source responses had reported completion output at the 512-token limit with reasoning usage (4,083 reasoning tokens out of 4,096 completion tokens aggregated over text sources). The reported data indicate the requested disabled-thinking flag did **not** yield non-reasoning short outputs on the Coding endpoint in this run; they do **not** reveal whether the API ignored the field, remapped it, or whether another transport detail caused this. Never label this run as validated no-thinking inference. The 512-token cap apparently truncated answers before useful A/B results.

## Engineering conclusion

Previously the GLM-5.3 run showed all eight Fresh/Neutral text holdouts timing out after full training (run 39937406266). Attempting GLM-5.2 disabled-thinking with a tight 512 cap did not solve control completeness and prevented text qualification. The next experiment should first issue a tiny **technical calibration** for a model documented to support per-turn disabled thinking (e.g., GLM-4.7) on the same route. Calibrate response availability for two control-shaped text prompts, with low generation cap and no raw outputs leaked; only then run a new 40-slot empirical trial under uniform mode. Both calibration and model change must be disclosed. Do not resend requests with previous run IDs, merge different models' outcomes as one treatment effect or claim G1 scientific acceptance.

No external auditor or gatekeeper is involved. The only gate is automatic readiness of the chosen provider/model mode before conducting more real requests.


## Thinking-parameter correction (2026-10-23)

**Historical results are preserved unchanged.** The request field
thinking.type=disabled in this experiment does **not** constitute
evidence that thinking was actually disabled; provider-returned
reasoning tokens demonstrate that no zero-reasoning condition was
verified. See G1_GLM_THINKING_MODE_CORRECTION_20261023.md.
For **future GLM-5.3** trials the project now always sends
thinking.type=enabled and explicitly selects reasoning_effort from
**low / high / max** only. Older-model experiments may not be
compared as identical compute conditions merely because they carried
a disabled request field. This correction changes no signed
observations, experiment denominators or scientific-acceptance status.
