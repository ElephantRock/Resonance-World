# D2d source capability acquisition envelope

D2d was a source-only calibration/characterization study motivated by the valid D2c `D2c-S1` result. It was designed to test whether 40, 80, or 160 labeled local-development cases could create >10 percentage points of held-out capability above a paired fresh control across four calibration schemas.

## Final status

The authoritative one-shot campaign `33701860334` completed on attempt 1, but all 384 experimental units ended in bounded provider-pair failures. The frozen evaluator therefore emitted **`D2d-A0 — acquisition_envelope_integrity_or_minimum_n_failure`** with 0 analyzable pairs in every schema. Evaluator integrity itself passed.

D2d is scientifically uninterpretable for acquisition efficacy: it does not show that 40, 80, or 160 cases succeed or fail. No common acquisition budget was established.

The D2d calibration schemas remain permanently excluded from a later D2e held-out confirmatory schema suite. Any future provider diagnosis or source-acquisition study must be a separately authorized fresh stream; same-request-stream rerun is prohibited.

D2d does not create destination agents, export Capability Artifacts, test reproduction, or qualify for a Mechanism Registry promotion. Registry authority is unchanged and production/default Historical Substrate remains **OFF**.

See `D2D_SOURCE_ACQUISITION_CLOSEOUT.md` and `evidence/` for the durable result record.
