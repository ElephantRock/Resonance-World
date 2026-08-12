# PIANO Phase 5 — Institutional Memory Result

## Completed artifact

- Workflow run: `31642962282`
- World revision: `7671f683c3dcc9c93a6de2a1f0245e8b6f443d88`
- Field revision: `e877bf03dbf6681ce7cbd98d984e73c032e911aa`
- Live artifact: `9159703582` / `piano-society-phase5-memory-live`
- Artifact digest: `sha256:b22f618199188272c048f0cb2d1b985abd5f750fab0623f34edbc76b07c096e0`
- Scientific interpretation eligible: true
- Advancement decision: **false**

## Frozen primary result

The experiment tested 24 paired organization × mission units after 100% roster replacement. Both arms used the exact same replacement roster, mission, strategy presentation, and 128 environment trial seeds. Only organization-owned procedure history differed.

| Measure | Memory reset | Memory retained | Retained − reset |
|---|---:|---:|---:|
| Mission success rate | 0.2666015625 | 0.2727864583 | **+0.0061848958** |
| Historical-best strategy selection | 0.50 | **1.00** | +0.50 |
| Cross-channel contradiction | 0.0416666667 | **0.00** | -0.0416666667 |
| Intent/action divergence | 0.0833333333 | **0.00** | -0.0833333333 |
| Outcome-report mismatch | **0.00** | 0.0416666667 | +0.0416666667 |
| Unsupported success claim | **0.00** | 0.0416666667 | +0.0416666667 |

Primary paired exact sign test:

- retained better: 5
- retained worse: 3
- ties: 16
- discordant units: 8
- two-sided p-value: `0.7265625`

Field-level mean effects:

- seed 12227: `-0.013671875`
- seed 12329: `0.0`
- seed 12433: `+0.0234375`
- seed 12539: `-0.005859375`
- seed 12641: `+0.033203125`
- seed 12743: `0.0`

Four of six field effects were nonnegative, satisfying that robustness component, but the primary effect was only +0.62 percentage points versus the preregistered +3 percentage-point minimum and the paired sign test was not significant.

## Mechanistic diagnosis

The null is **not** a failure of the PIANO controller to read institutional memory.

The retained arm selected the mechanically derived historical-best strategy in 24/24 units and had zero controller-to-action divergence. Memory therefore exerted strong decision control.

The bottleneck is portability across complete turnover:

- memory changed the selected strategy in 12/24 paired units;
- four of those 12 strategy changes still routed to the same replacement-member pair under W5, so they could not change the environment-facing action;
- only 8/24 units therefore produced a different routed pair;
- among those eight effective routing interventions, retained memory improved five and worsened three, with mean success lift only about +1.86 percentage points;
- diluted across all 24 preregistered units, the primary effect was +0.62 percentage points.

Exploratorily, larger historical specialist-vs-balanced success-rate margins were positively associated with transfer benefit. That pattern is post-hoc and must **not** be used to tune a threshold on the Phase-5 dataset.

One retained record also set `claims_success=true` despite an audited mission success rate below the frozen 0.5 grounding threshold. The preregistered report-mismatch degradation remained within its +0.05 limit, so this did not determine the advancement failure.

## Architectural conclusion

Raw context-indexed policy success rates are too weak a representation of organization memory for complete membership turnover. They tell a new controller **which procedure historically won**, but not **under what capability conditions that procedure was applicable**.

The next experiment therefore remains within Phase 5 and tests a revised memory primitive rather than advancing to a broader institutional scale:

> **Applicability-aware procedural memory** should preserve identity-free execution preconditions alongside procedure outcomes, allowing a new roster to judge whether historical procedure evidence transfers to its current capability geometry.

Phase 5B must use fresh source Fields and a new preregistered confirmatory split. The completed Phase-5 confirmatory organizations may be used only for diagnosis and may not be reused as confirmatory evidence.
