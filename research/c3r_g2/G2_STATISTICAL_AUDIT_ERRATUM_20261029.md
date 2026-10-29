# ERRATUM — G2 interaction statistical audit power simulation (2026-10-29)

Status: **correction appendix, documentation only.** The historical
files (`G2_STATISTICAL_AUDIT_RESULT_20261029.md`,
`statistical-audit.json`, and the audit script at commit `521857f`)
are NOT modified. The G2 live line remains CLOSED by the owner's
investment decision; nothing is re-run; G2 is not reopened.

## The flaw (owner-identified, confirmed)

In `scripts/audit_g2_interaction_statistical.py`
(`simulate_org_stratified`, commit `521857f`):

```python
g_env = _clip01(rng.gauss(cell["g_mean"], cell["g_sd"]))
g_env = 2 * g_env - 1
```

`G = D_VAR − D_CTX` is a performance DIFFERENCE already living on
[−1, +1]. The code treated it as a probability on [0, 1], clipped it
into [0.01, 0.99] — destroying every negative value (floor at 0.01) —
and then applied an affine map to [−0.98, +0.98]. Consequences on the
20 measured band means (deterministic arithmetic, no re-run needed):

- every positive mean INVERTED: +0.40 → −0.20, +0.55 → +0.10,
  +0.05 → −0.90 …
- the one negative mean (−0.05) clipped to the floor and mapped to
  −0.98;
- **the mean of the G inputs into the gate simulation flipped from
  +0.353 to −0.289.**

A second, lesser flaw: the simulation approximated the G and
net-value variances as INDEPENDENT normals instead of preserving
their measured joint distribution.

## What is and is not affected

- **INVALID as evidence:** the conclusion "the full hierarchical gate
  cannot reach 80% power within the 2,500-send cap" — it was computed
  on sign-corrupted inputs and must not be cited as proof of
  unfundability.
- **UNAFFECTED:** the owner's closure of the G2 live line (an
  investment and design decision, standing on its own); the corrected
  C-failure semantics and direction tests; the joint/hierarchical
  gate logic itself; the cost/time corrections; all prior G2 stages
  (qualification, probe, calibration, no-forced-sign check).
- **Standing scientific record:** the live calibration's mirror
  finding (±39pp by evidence class) and the exploratory interaction
  analysis remain valid — they were measured, not simulated.

## Discipline note

Any future power simulation for the resilience design must: keep
differences on their natural [−1, +1] support; draw G and net value
from their measured JOINT distribution (or bounded models thereof);
and include a sign-preservation unit test (transformed-input means
must equal source means within tolerance) before any verdict is
issued. The corrected simulation, if ever needed, belongs to the NEW
design's preparation — not to reopening G2.
