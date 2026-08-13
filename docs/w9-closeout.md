# W9 Closeout — Accepted

Status: **COMPLETE — ACCEPTED**

W9 closes with its preregistered negative/mixed result preserved. The accepted scientific
state is documented in `docs/w9-status.md` and was merged through PR #105 as
`410006144e930fc0a52ffea9c2fae70fb6a58d5b`.

## Acceptance evidence

The final pre-merge exact head was
`eaaa0c013cd878a5d0e1afa88bfc6d54e90ae371`.

The dedicated W9-07 workflow `31654273741` executed two isolated unseen-replication jobs
and a downstream acceptance job. All three passed:

- primary reproduction: **PASS**
- independent reproduction: **PASS**
- byte-identical authoritative-output comparison: **PASS**

Artifacts:

- primary `9163835188`, digest
  `sha256:550da9bfb7ad64dfde8f2c8c48e4ba75de28fb25097152455d0cd3abd6c0487a`
- independent `9163824319`, digest
  `sha256:e8042d2e9591864b244485c2a79472b2877636ca70b486834bb3f83701cbbd16`

The comparison gate required byte identity for W9-00B, W9-01, W9-02, W9-03, W9-04,
W9-05, W9-06, the W9-07 synthesis, and its manifest. The accepted W9-07 synthesis SHA-256
is:

`0400ad83885dc81a0c8a139431f98545b0a948e1698a4522631fc8e413c10c44`

The accepted manifest SHA-256 is:

`da518137aaf23fdfc679f7a5b227f36bb9f4e81497bb1f2f6886adca4defe81e`

Fresh exact-head Codex review reported no major issues, and the final acceptance-path
review thread was resolved before merge.

## Scientific closeout

The nested W9 outcomes are:

- `replicated_calibrated_criticality_pricing = true`
- `replicated_tradeoff_reduction = false`
- `replicated_sustainable_capability_leasing = false`
- `replicated_regenerative_allocation = false`

No failed mechanism was retuned, relabeled as a pass, or promoted into the integrated
regime. The discovery-frozen W9-05 selected mechanism set remained empty through unseen
replication.

## Cleanup boundary

This closeout removes only temporary W9 campaign-specific GitHub Actions workflows that
were used to execute the completed research campaign. Scientific source code,
configurations, preregistration, tests, and accepted result semantics remain in the
repository.

No new W9 scientific claim is introduced by closeout, and this document does not claim a
new post-merge scientific regeneration. The accepted evidence is the exact-head
reproduction and byte-comparison gate described above, followed by the squash merge of
that accepted state.
