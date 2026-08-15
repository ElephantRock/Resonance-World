# H6 post-H5 motivation record

This document records the exploratory observations inspected **only after** H5 had received its immutable registered classification. They motivate H6 but are not H6 evidence and cannot alter H5.

Frozen H5 source: candidate `7afa2d139049b1fdb80de2a95d76b49430b6a046`, run `31764482769`, classification `historical_substrate_institutional_mediation_failed`.

At g3, H5 persistent versus static correctness was:

- `routine_transfer`: 8/12 versus 6/12;
- `authority_conflict`: 9/12 versus 11/12;
- `cross_role_composition`: 3/12 versus 6/12;
- combined non-routine: 12/24 versus 17/24.

H5 Gate 10 evidence-reference integrity failed. Direct inspection of the frozen live artifact found 40/1,296 calls with at least one invalid free-form evidence identifier. Of those 40 calls, 34 were chair calls; arm counts were direct 24, roles-only 6, governed-persistent 6, governed-static 4; generation counts were g1 22, g2 16, g3 2. Every invalid identifier inspected was an unknown/abbreviated/hallucinated identifier rather than a valid record from the other analyst partition.

Because this failure was strongly skewed toward the direct arm and early generations, it cannot be used post hoc to excuse the persistent-versus-static g3 reversal. H6 therefore normalizes evidence references across all treatments with deterministic E1–E6 slots and tests a new relevance-dependent state-channel mechanism prospectively.

No H5 call is removed, repaired, or rescored.
