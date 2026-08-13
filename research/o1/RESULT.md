# O1 — ContextGraph Observatory Reconstruction Validity

Status: **accepted PASS**

Classification: `observatory_registered_reconstruction_pass`

Preregistration: #119  
Program architecture: #111  
Threshold governance: #118  
Reviewed exact head: `1936962481e7e26177e414fbd420912729d9be65`  
Execution PR: #120  
Squash merge to `main`: `e10e564f3a7920ff7d542bb78bb1db259ebc8d35`  
Authoritative workflow run: `31682533677`

## Accepted result

All eight registered O1 gates passed:

1. observer-only/non-interference boundary retained;
2. evidence completeness and provenance;
3. byte-exact admissible-event reconstruction parity;
4. exact entity/relationship/authority/organization-lineage parity;
5. exact observable aggregate parity;
6. historical preselected summary reproducibility after evaluator-key join;
7. hidden-state/answer-key exclusion;
8. two isolated exact-head reproductions with downstream byte comparison.

The two authoritative reproduction artifacts were:

- primary artifact `9174045021`, artifact digest `sha256:63be5b2673a477dffea85545abdf15c2116dbc6177680584648fc332f801fd97`;
- independent artifact `9174046228`, artifact digest `sha256:022451f042e63df1aa75d0cb361778699e0ebf37f94cc3a38ef7d7a2e9f38894`.

The ZIP artifact digests differ because artifact-container metadata is not authoritative. The dedicated downstream comparator verified byte identity for every registered authoritative file inside the two reproductions.

The accepted reconstruction contained 8,160 direct, provenance-bearing claims, exactly matching the registered expected claim count.

## Historical-summary reconstruction

After reconstruction products were frozen and Plane K became available only to the evaluator, O1 reproduced the preselected historical summaries required by #119, including:

- corrected Phase 4C authority: unsigned role failures `29/60`, unsigned spoof captures `29/60`, attested role failures `0/60`, attested spoof captures `0/60`;
- Phase 5C complete-turnover result: reset success `0.2776692708333333`, retained success `0.3030598958333333`, retained-minus-reset `0.025390625`, paired better/worse/ties `9/0/3`, and complete turnover for every registered organization;
- W9-06 observable service totals: `9580/12288`, `9485/12288`, and `9561/12288` for the three registered organizations, over 72 organization service cycles and 216 external agent-cycle exposures.

Five W9 quantities remain explicitly **not observationally identifiable** from admissible evidence and were not reconstructed:

- `compute_normalized_world_stock_growth`;
- `developmental_efficiency`;
- `mean_source_loss_pp`;
- `service_efficiency`;
- `source_accessible_capability_growth`.

## Scientific claim and boundary

O1 establishes **registered observer-side reconstruction validity** for the frozen benchmark families only.

It does **not** establish universal observational sufficiency, historical-memory efficacy, ContextGraph performance benefit, sustainability improvement, latent capability inference, or permission for participant/controller historical access.

The causal boundary remains unchanged:

- `INTEGRATION_MODE = observer-only`;
- `HISTORICAL_SUBSTRATE_ENABLED = False`;
- participant ContextGraph query access is disabled.

The exact machine-readable accepted result and manifest are committed as `result.json` and `manifest.json`. Frozen pre-outcome benchmark provenance remains in `provenance.json`.

## Program continuation

O1 closes the reconstruction-validity stage. The next Observatory stage is O2: longitudinal scientific utility. Historical-substrate/H-series feedback remains blocked until separately preregistered and authorized.
