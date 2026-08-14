# H7 execution record

Status: **hosted apparatus locked; zero H7 provider calls; classifiable campaign not yet triggered**.

Frozen preregistration: issue #156. Scientific base: `935e0463acc88f7f7756861d734eeba7b4efb034`. H6 immutable scientific candidate: `ff6bd5e030c3159829460e123f2fadd2e8087f93`.

## Prospective fresh fixture identity

Local deterministic materialization before hosted execution produced:

- Plane E SHA-256: `88372db1e7f283ddd0a2ee0427d51a41a9b9d36431e6a1b62c22f3dcea891de8`
- Plane K SHA-256: `8a5093d4e4b25d61a195ce2a17b4567d3b6775ce927674751f32f1b246a1ead4`
- fixture manifest SHA-256: `cd5f3a218cdb1f032c30be116e41442e74436d88a8f9b15e4ac58c4238045f64`
- organization decision cells: 432
- logical model calls: 1,296
- canonical record budget: 6 per unit
- authority grants: 12
- fresh replicates: 12

## Hosted credential-free apparatus lock

Apparatus candidate `8c63539e606e481ff25d5c68c87bd5c5ff9168e9` ran as workflow `31797399097`. The apparatus-lock job completed successfully; the live-provider and frozen-output-evaluator jobs were skipped because the commit did not contain `[H7-RUN]`. Therefore zero H7 provider calls occurred.

Hosted materialization reproduced the local fixture identities byte-for-byte. Hosted provenance:

- Plane E SHA-256: `88372db1e7f283ddd0a2ee0427d51a41a9b9d36431e6a1b62c22f3dcea891de8`
- Plane K SHA-256: `8a5093d4e4b25d61a195ce2a17b4567d3b6775ce927674751f32f1b246a1ead4`
- fixture manifest SHA-256: `cd5f3a218cdb1f032c30be116e41442e74436d88a8f9b15e4ac58c4238045f64`
- hosted lock verification SHA-256: `962a4b19b3f7df3e042cd0677f2162ac0c6244d3f014ab4ccc4a11156612e281`
- hosted pre-key request-plan SHA-256: `304a67ffbf3fbb878784550fe931bdaad6a7243c56f9cd77f07b1f8bf606812c`
- Plane E/request-plan artifact: `9217891849` (`sha256:d7073ccd6802d978c030e5d241d883355404a9f1b182bb307129140569e4343a`)
- Plane K artifact: `9217892128` (`sha256:e9d2257169dade0fec34dc0d9398eece8db56e91207ebfca23dceac1cee574fe`)
- fixture-meta artifact: `9217892415` (`sha256:1273ade8ad5b1c45861a48536bd0e9f9e7861c2851a464fe478d0ffa5a484148`)

Credential-free assertions passed before provider access: 144 matched `(unit, replicate)` blocks, balanced three-arm rotation, state exposure exactly `always_state=144`, `selective_state=48`, `no_state=0`, analyst prompts/role partitions identical across arms within blocks, non-routine selective/no-state deterministic protocol and chair scaffold byte-identical, routine selective/always deterministic protocol and chair scaffold byte-identical, evaluator truth/private sentinel absent from the request plan, and production/default Historical Substrate OFF.

The prospective implementation clarification defining deterministic chair-scaffold identity separately from independently sampled analyst reports was posted on #156 before implementation and before any provider calls.

A provenance-only update does not carry `[H7-RUN]`; any workflow it triggers remains apparatus-only. The exact classifiable scientific candidate will be posted prospectively on #156 before its branch ref is advanced.

Production/default Historical Substrate remains OFF.
