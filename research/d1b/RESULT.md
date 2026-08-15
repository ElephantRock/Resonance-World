# D1b result — fresh replication of capability reproduction

Status: **complete classifiable confirmatory replication**.

Study classification: **`D1b-S3` / fresh capability-reproduction replication supported**.

The unchanged frozen D1 evaluator emits its original internal label `D1-S3 / d1_capability_reproduction_supported`; for D1b this is mapped one-to-one to `D1b-S3` because the study identity is a fresh replication of the exact D1 mechanism, not a new discovery study.

Authoritative preregistration: issue #163. Exact classifiable D1b candidate: `00a5d84e09939e51d54cc59c7ecf1e27f6acbd3c`. Authoritative workflow: `31861974865`.

## Replication design

D1b reused the exact D1 scientific apparatus with no outcome-driven retuning:

- 36 fresh independent source/destination Field pairs;
- seeds `50000..50035`, disjoint from D1-0 development seeds and D1 confirmatory seeds;
- exact 12/12/12 balance across the three opaque skill aliases;
- same deterministic ecology and development law;
- same `d1-capability-artifact-v0.1` treatment/export boundary;
- same source-developed, reproduced-protocol, fresh-no-development, and diagnostic private-state-oracle arms;
- same fixed P0→P1→P2 sequence, one-sided alpha 0.05;
- same normal and fixed-seed 100,000-replicate percentile-bootstrap lower-bound gates;
- same conventional P2 non-inferiority margin `0.05931396484374999`;
- fixed n=36, no early stopping.

## Registered replication outcome

Mean held-out specialist success rates:

| arm | mean |
|---|---:|
| `fresh_no_development` | 30.111% |
| `source_developed` | 90.495% |
| `reproduced_protocol` | 89.605% |
| `private_state_oracle` | 90.169% |

The private-state oracle remains diagnostic and product-ineligible.

### P0 — source capability production

Estimand: mean(`source_developed - fresh_no_development`).

- estimate: **+60.384pp**
- n: 36 Field pairs
- normal two-sided 95% CI: **[+59.055pp, +61.713pp]**
- normal one-sided 95% lower bound: **+59.268pp**
- fixed-seed 100,000-replicate bootstrap two-sided 95% CI: **[+59.039pp, +61.643pp]**
- bootstrap one-sided 95% lower bound: **+59.266pp**
- registered gate: **PASS**

### P1 — destination capability acquisition

Estimand: mean(`reproduced_protocol - fresh_no_development`).

- estimate: **+59.494pp**
- n: 36 Field pairs
- normal two-sided 95% CI: **[+57.541pp, +61.448pp]**
- normal one-sided 95% lower bound: **+57.855pp**
- fixed-seed bootstrap two-sided 95% CI: **[+57.444pp, +61.263pp]**
- bootstrap one-sided 95% lower bound: **+57.813pp**
- registered gate: **PASS**

### P2 — reproduction fidelity

Estimand: mean(`reproduced_protocol - source_developed`).

Registered non-inferiority boundary: **−5.9314pp**, inherited unchanged from D1's prospectively frozen 90% reproduction-fidelity product convention. The margin remains classified **conventional**.

- estimate: **−0.890pp**
- n: 36 Field pairs
- normal two-sided 95% CI: **[−2.712pp, +0.933pp]**
- normal one-sided 95% lower bound: **−2.419pp**
- fixed-seed bootstrap two-sided 95% CI: **[−2.778pp, +0.814pp]**
- bootstrap one-sided 95% lower bound: **−2.441pp**
- both lower bounds are above the preregistered −5.9314pp boundary
- registered non-inferiority gate: **PASS**

The descriptive fidelity ratio `(reproduced-fresh)/(source-fresh)` was `0.985265`. D1b does not establish equality or superiority of reproduced over source capability; it establishes the preregistered non-inferiority claim only.

## Integrity result

All frozen evaluator gates passed:

- exact candidate identity;
- exact D1b plan/lock identity;
- 36 unique fresh confirmatory seeds;
- development/confirmatory disjointness;
- exact 12/12/12 skill balance;
- source/destination identity disjointness in every pair;
- source identity, reconstructive source/environment seed, private practice state, conversation state, evaluator truth, and evaluation answers absent from the Capability Artifact;
- Capability Artifact schema intact;
- private-state oracle product-ineligible;
- deterministic execution integrity;
- production/default Historical Substrate OFF.

Artifact target inference matched the source capability target in all 36 replication pairs; this is descriptive only.

## Descriptive skill breakdown

No skill-level contrast was preregistered as confirmatory.

- `skill-a`: fresh 30.729%, source 89.225%, reproduced 90.332%, oracle 88.867%
- `skill-b`: fresh 29.557%, source 90.397%, reproduced 89.355%, oracle 90.039%
- `skill-c`: fresh 30.046%, source 91.862%, reproduced 89.128%, oracle 91.602%

These subgroup values cannot rescue or upgrade any pooled primary result.

## Provenance

- scientific candidate: `00a5d84e09939e51d54cc59c7ecf1e27f6acbd3c`
- authoritative workflow: `31861974865`
- parent D1 plan SHA-256: `8223d441f8399d89901ecd7f704d8744c571a8035c7ebdc94150435f92ba8858`
- D1b plan SHA-256: `e3e7a0698d2cb89b58da973aeef6f4d48ddc6a4f6946212657eb952aeef45bdb`
- D1b lock SHA-256: `8cea47bed19b054b68023a39a64de1b9b17ab9cb40db737b076075332e5df393`
- frozen confirmatory output SHA-256: `a212be892c04c63a66daacf99b9db30bc4b4a0344c8642392e42e257ded8aebb`
- result SHA-256: `56e85a609c32b7dc62c16b94f07efa16c7f550497c8dc81eeb84517bd13dc200`
- audit SHA-256: `34b9e40c4ed35271d0b38c6e0c86433d010063d63f942c8d489ac6b48ee323f0`
- manifest SHA-256: `320ca765c1a2c67a857bc894d222e7d4eb15a0199c6bd0a41010fe3e0c60cd6a`
- apparatus artifact: `9240852006` (`sha256:1a5554c077d7b9184bb0af4744472ebc9b1cab6dbe5a573a9f1b5aec5d811d3f`)
- confirmatory-output artifact: `9240856188` (`sha256:30e687a2b5de96c612ab34972152373808001e10b50d7b6e2f364f9c569a31c4`)
- evaluation artifact: `9240861461` (`sha256:8381d848bd386a5f4274a7634e622f10ef4d400f4696f799f9485676f4cba146`)

The confirmatory output was executed twice and byte-compared. The unchanged D1 evaluator then ran twice over the frozen D1b output and produced byte-identical result/audit/manifest records with matching exit status 0.

## Bound replication claim

In a fresh preregistered 36-pair cohort, the exact D1 Capability Artifact/development mechanism again established source capability production and destination acquisition, and reproduced capability remained non-inferior to source-developed capability under the prospectively conventional 90% fidelity criterion.

The conjunction of D1 and D1b therefore supports **fresh internal replication within the controlled deterministic individual-specialist substrate**. This does not establish stochastic/model-based capability learning, semantic knowledge transfer, team or institutional reproduction, naturalistic transfer, or environment spawning.

D1b does not self-promote the Mechanism Registry. D1+D1b are now eligible for independent acceptance review toward `internally_replicated`, subject to the required proposer/acceptor separation.

No D1b confirmatory retuning or rerun is authorized after classification. Production/default Historical Substrate remains OFF.
