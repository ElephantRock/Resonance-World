# W6 Authoritative Post-Merge Validation

W6 completed as a valid **mixed** campaign. The authoritative synthesis status is
`w6_discovery_not_replicated`: the individual mobility findings replicated, while the
W6-06 PairModule route-consistency criterion did not.

## Validation provenance

- W6 implementation PR: #56
- merged W6 science commit: `5db6a4b7f0bd65e5c453dbfa6cfcb94d61e713f1`
- post-merge validation PR: #59
- validation head: `aa61ad3d6753fac6ae4146dc5443ff2303e0c912`
- hosted CI run: `31494258350`
- Ruff + pytest: **PASS**
- complete W6 campaign: **PASS**
- discovery regenerated: 6 Fields / 72 fresh agents
- replication regenerated in a fresh PostgreSQL store: 6 Fields / 72 additional agents
- evidence artifact: `9102321419`
- artifact digest: `sha256:4fd39b69b9a20f2fbd330fbceba5b69e76f5f1218c951ff22d22cfd3af902471`

The validation branch was reset exactly to merged `main` before a documentation-only
marker was added. No scientific code, configuration, seed, mission, selector, threshold,
curriculum, mobility semantic, or outcome law differed from the merged W6 state.

## Immutable scientific outputs

The authoritative post-merge run reproduced the established scientific outputs
byte-for-byte:

- discovery JSON SHA-256:
  `111d956bae44db8c5ae2a261cc657c5fe1ac77acd6cfa6946a20749ce3cf691a`
- W6-07 replication JSON SHA-256:
  `0453f1bb5b466079819ab480bfdc97bc62132e2b9c2fd23fef5cb7ad5c39bc58`
- synthesis JSON SHA-256:
  `8f12f8c91c7829b263bbaa8653cd832ab1b974e8a60a775b2c38f0b98d66776a`

This was the fourth complete execution with the same three scientific JSON outputs.

## Accepted interpretation

- **W6-02:** secondment and temporary-migration first-window outputs were exactly equal;
  mobility metadata did not leak into the outcome law.
- **W6-03:** source Fields experienced short-run absence costs, but the fixed local
  recovery curriculum removed persistent loss. Persistent brain drain is not supported
  under the tested recovery mechanism.
- **W6-04:** explicit destination-acquired, provenance-bearing agent-owned learning
  returned a replicated source benefit: +3.0377 pp in discovery and +4.2531 pp in unseen
  replication, with 3/3 routes positive in both phases.
- **W6-05:** the preregistered brain-circulation gate was satisfied in both phases.
- **W6-06:** intact PairModule mobility was positive in aggregate but not route-general;
  only 1/3 unseen routes was positive, so the frozen route-consistency gate failed.

The W6-06 criterion was not weakened after observing the result. W6 therefore supports
**brain circulation through explicit returned individual learning**, while retaining the
negative boundary that pair-unit mobility is not yet robust across routes.

Resonance Field remained unchanged throughout W6.
