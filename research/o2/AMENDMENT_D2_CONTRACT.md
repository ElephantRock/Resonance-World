# O2 post-outcome D2 contract amendment

Parent preregistration: #122
Prior boundary amendment: #125
Reviewed candidate: `9c16089f24daf597b91b0dfde27d3764aa0d6729`

The exact-head scientific/code review found that D2 was implemented with a whole-run member contribution vector, while #122 preregistered the stronger longitudinal requirement "exact contribution vector by interval." The reviewed candidate is therefore retained as an internally passing candidate but is not accepted as the registered O2 PASS under the original D2 contract.

This amendment preserves the original Plane E histories, R0 endpoint aggregates, R1 flat logs, semantic templates, opaque relabelings, all prior outcomes, and all non-D2 query semantics. It restores the missing D2 longitudinal query as `contribution_vector_by_interval`, defined as the exact observable per-member success-count vector for each registered interval, with all registered members represented explicitly at every interval.

The amendment is evaluator-contract only. A deterministic amendment materializer may add the D2 query to the query manifest and derive the corresponding Plane K answer from the already-frozen Plane E history. Plane E, R0, and R1 roots must remain byte-identical to the original lock. The amended Plane K and meta roots must be frozen before the amended authoritative acceptance rerun.

Researcher-side computation of `contribution_vector_by_interval` must be generic over admissible performance/membership events and must occur before Plane K is restored. R0 must continue to report the query as `not_observationally_identifiable`. R1 and R2 may answer it from their admissible longitudinal events. Exact support provenance is the complete set of performance-event IDs used to construct the interval vectors.

No scientific benchmark retuning is authorized. The original lock and prior candidate runs remain immutable historical records. Historical Substrate remains disabled and participant/controller ContextGraph access remains forbidden.
