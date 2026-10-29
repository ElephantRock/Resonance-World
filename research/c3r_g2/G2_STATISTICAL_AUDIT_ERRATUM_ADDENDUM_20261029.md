# ERRATUM ADDENDUM — precision on the distorted means (2026-10-29)

Status: **clarification appendix (new document; the original ERRATUM
and all historical files remain untouched).**

The original ERRATUM says positive means were "INVERTED". The owner's
review correctly notes this is imprecise: the affine map
`2·clip01(x) − 1` is monotone, so means above 0.50 stay positive
(e.g., **+0.55 → +0.10**); means between 0.01 and 0.50 flip sign
(+0.40 → −0.20, +0.05 → −0.90); negative means are floored to 0.01
and mapped to −0.98.

The material facts are unchanged and correctly stated: (1) the
transformation SYSTEMATICALLY DISTORTS every G input (compressing,
sign-flipping the sub-0.5 majority, flooring negatives); (2) the
OVERALL mean of the gate inputs flipped from **+0.353 to −0.289**.
The audit's "no 80% power under the cap" conclusion therefore remains
WITHDRAWN as evidence, and the G2 closure remains an investment
decision, not a scientific impossibility result.
