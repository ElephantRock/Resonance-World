# PIANO Phase 5 result: institutional memory after complete turnover

Status: **scientifically interpretable; advancement gate not met**.

This result is the terminal confirmatory outcome for preregistration `glm5.2-institutional-memory-v1`. It must not be reclassified or tuned post hoc.

## Bound execution

- World branch head used for the successful run: `7671f683c3dcc9c93a6de2a1f0245e8b6f443d88`
- Resonance Field revision: `e877bf03dbf6681ce7cbd98d984e73c032e911aa`
- Workflow run: `31642962282`
- Live artifact: `9159703582` (`piano-society-phase5-memory-live`)
- Live artifact digest: `sha256:b22f618199188272c048f0cb2d1b985abd5f750fab0623f34edbc76b07c096e0`
- Frozen source capsule SHA-256: `c41c50165c0fb93d49848bb44b0fcd58172402fa52f7f05fd5f3456222b78c0d`
- Model snapshot: `glm-5.2`
- Paired units: 24 = 6 confirmatory organizations × 4 missions
- Turnover: 100%
- Evaluation trials per arm/unit: 128, paired by common random numbers

## Frozen primary result

| Metric | Memory reset | Memory retained | Retained − reset |
|---|---:|---:|---:|
| Mission success rate | 0.2666015625 | 0.2727864583 | **+0.0061848958** |
| Historical-best strategy selection | 0.50 | 1.00 | +0.50 |
| Cross-channel contradiction | 0.0416666667 | 0.00 | -0.0416666667 |
| Intent/action divergence | 0.0833333333 | 0.00 | -0.0833333333 |
| Outcome-report mismatch | 0.00 | 0.0416666667 | +0.0416666667 |
| Unsupported success claim | 0.00 | 0.0416666667 | +0.0416666667 |

Primary exact paired sign test: better = 5, worse = 3, ties = 16, discordant = 8, two-sided `p = 0.7265625`.

Field-level retained-minus-reset effects:

- `w4-source-seed-12227`: -0.013671875
- `w4-source-seed-12329`: 0.0
- `w4-source-seed-12433`: +0.0234375
- `w4-source-seed-12539`: -0.005859375
- `w4-source-seed-12641`: +0.033203125
- `w4-source-seed-12743`: 0.0

Four of six field effects are nonnegative.

## Advancement decision

The preregistered gate required all of:

1. mean mission-success effect ≥ +0.03;
2. exact paired sign-test p ≤ 0.05;
3. at least four nonnegative field effects;
4. outcome-report-mismatch delta ≤ +0.05.

The run satisfies (3) and (4), but fails (1) and (2). Therefore:

`advance_beyond_phase5_institutional_memory = false`

No threshold may be relaxed after observing this result.

## Interpretation

Phase 5 separates two questions that were previously entangled.

First, the PIANO institutional controller **can consume and obey organization-owned procedure history**: the retained arm selected the historically best strategy in 100% of units versus 50% in the reset arm, while also eliminating cross-channel contradiction and intent/action divergence.

Second, the particular memory representation tested here—context-indexed success rates for routing policies learned on the pre-turnover roster—**does not transfer strongly enough through complete membership replacement**. On the 12 units where retained memory changed the selected strategy relative to reset, the mean mission-success effect was only about +0.01237; several historical-best choices were neutral or harmful on the replacement roster.

The scientific conclusion is therefore not “institutional memory does not work.” It is narrower: **remembering which policy won on the old roster is an insufficient transferable institutional representation under 100% turnover**.

## Next experimental constraint

Any follow-up must remain inside Phase 5 rather than claiming advancement. A valid Phase 5B should use fresh source organizations and test a memory representation that stores transferable evidence about the relationship between mission demands, roster capability structure, routing decisions, and outcomes—not merely a stale winning-policy label. The environment must still never read memory directly, and the reset/retained arms must still share the exact replacement roster and outcome law.
