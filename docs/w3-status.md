# W3 Campaign Status

Status: **VALID CAMPAIGN COMPLETE / SWARM ADVANTAGE REPLICATED / INDEPENDENT RELATIONSHIP CAPITAL NOT REPLICATED**

- Parent issue: #16
- Experiment count: 7
- Discovery source Fields: 5 x 12 agents = 60 agents
- Replication source Fields: 3 x 12 agents = 36 unseen agents
- Frozen swarm recruiter: beta = 0.5
- Frozen recruiter SHA-256: `f716ff427c79358122c4e7a95eebaeff41f3d7f51c1ea85a30d93167b07c25c4`

## Hosted validation

- PR implementation CI run: `31463354335` — PASS
- First valid complete W3 run: `31463354353` — PASS as an execution campaign
- W3 evidence artifact: `9090650001`
- Evidence artifact digest: `sha256:0f26c3e2c3102dd1a04b13f4eedb007b7ab2cf023bdb0c5fea03e4665cdca7e9`

An earlier run (`31463185246`) produced the same positive held-out discovery result but failed before W3-07 because the replication source manifest omitted an auxiliary `holdout_seeds` set required by the pinned Field parser. Commit `6accfd688fd2820571933492f937ba4148caed4b` repaired only that parser invariant. No W3 mission, destination law, recruiter weight/grid, threshold, discovery result, or replication identity changed.

## W3-01 — recruiter freeze

Calibration selected `beta = 0.5`.

- beta = 0.0: 58.44% calibration success
- beta = 0.25: 60.12%
- beta = 0.5: 60.95%
- beta = 0.75: 57.53%
- beta = 1.0: 57.61%
- beta = 1.25: 58.02%

The frozen recruiter was reproduced exactly after the manifest repair.

## Held-out discovery — PASS

- W3-02 swarm vs best recruited individual: **+10.00 percentage points**
  - Field 484: +7.16 points
  - Field 605: +12.84 points
- W3-03 relationship-aware swarm vs competence-only assembled pair: **+3.70 points** — PASS
- W3-04 correct relationship edges vs shuffled edges: **+13.21 points** — PASS
- W3-05 private-state oracle advantage over public recruiter: **+0.99 points**
- W3-06 intact swarm vs best individual under drift: **+9.81 points** — PASS
- W3-06 one-member-loss degradation: **8.89 points**
- W3-06 survivor vs best-individual comparator: **+0.93 points**

The corrected run reproduced the entire held-out discovery summary exactly.

## W3-07 unseen replication — RELATIONSHIP-CAPITAL GATE FAIL

Post-freeze source Fields: 726, 847, and 968. Replication missions require four skill areas and used the unchanged beta=0.5 recruiter.

- recruited swarm vs best recruited individual: **+8.77 points**
- Field 726: **+16.11 points**
- Field 847: **+2.41 points**
- Field 968: **+7.78 points**
- positive Fields: **3/3**
- correct relationship edges vs shuffled-edge selector: **+5.93 points**
- relationship-aware swarm vs competence-only assembled pair: **-0.37 points**
- preregistered W3-07 replication gate: **FAIL**

## Interpretation

W3 provides replicated evidence that two-agent swarms selected from public developmental evidence outperform the best recruited individuals in this deterministic skill-practice-plus-coordination model. However, the stronger hypothesis that historical relationship identity contributes independent portable value beyond competence and complementarity did not replicate: relationship-aware selection was slightly worse than the competence-only pair baseline on unseen W3-07 missions.

The shuffled-edge result indicates that relationship information still contains selection signal, but it is not sufficient to establish independent transferable relationship capital under the preregistered control.

Therefore the correct W3 synthesis is **`w3_relationship_capital_not_replicated`**, not `replicated_transferable_relationship_capital`.

No stronger relationship-capital claim is permitted without a new preregistered campaign.

## W4-00 architecture clarification

W4-00 established that Resonance Field does **not** currently carry native persistent pair-level learned state. In W3, `coordination_exposure` was derived by Resonance World from successful requester↔winner interaction counts and then used by the World destination law as an explicit coordination bonus. It was therefore a **World-derived experimental proxy**, not a Field-native relationship phenotype.

This clarification does not alter any W3 numerical result or the `w3_relationship_capital_not_replicated` synthesis. It narrows the mechanism claim:

> W3 replicated a two-agent swarm advantage under a World destination model containing an explicit coordination-exposure proxy; it did not demonstrate spontaneous emergence or transfer of partner-specific relationship state from the current Resonance Field runtime.

The canonical machine-readable boundary is `configs/w4/relationship-state-audit.json`, validated by `resonance_world.w4_architecture_audit`.
