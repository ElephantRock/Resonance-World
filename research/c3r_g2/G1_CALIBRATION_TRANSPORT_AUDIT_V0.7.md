# C3R G1 — Calibration transport reconciliation v0.7

**Status:** offline technical audit; no provider execution, externally attested billing, G1 evidence, or scientific promotion. Changes remain in draft PR #310.

## Scope

The historical GLM-5.3 512-token diagnostic recorded 8 prescribed logical tasks and 6 self-reported physical sends, yielding 5 parseable answers but 0 complete learned/fresh qualification pairs. This work does **not** repeat or change that experiment.

The prospective, separate technical calibration in v0.5 contains two public prompt formats: arithmetic and text operations. For each family it prescribes one development-format prompt and three nominal qualification-format prompts under learned/fresh/placebo labels, totaling eight logical requests. There is no graded source feedback, independently held-out answer key or G1 causal inference in this calibration.

The module src/resonance_world/c3r_g1_calibration_audit.py recomputes and checks:

1. The plan lock, stage, family, arm and exact task identifier for every prescribed row.
2. The SHA256 of the complete canonical provider request body, reconstructed for each reserved send from its public prompt and reviewed model, thinking, temperature, streaming and output-budget settings. It must equal the corresponding physical reservation digest.
3. All eight attempt rows and independently recomputed per-family, per-arm, complete-triplet and overall counts, including failed and unsent attempts.
4. Normal termination for any accepted exact-A/B output: finish_reason must explicitly equal stop, never missing, truncated or filtered.
5. A fail-closed terminal stop at the first wrong-model, malformed, truncated or adapter-failed result; all remaining rows must be marked not_sent_after_failure without invented provider metadata.
6. HTTP and physical-ledger ordinal/status consistency, including terminal EmptyFinalOutputLengthCap and HttpNon200 failures. No reserved-but-unclosed entry can silently count as a response.
7. All construction-only caveats and permanently false science/provider-authorization fields. An offline constant-A fixture with zero send reservations cannot pass as transport evidence.

The successful audit verdict is **structurally_consistent_unattested**. That means only that the submitted report and self-produced ledger match the frozen local transport contract. It never implies that the vendor received the requests, was billed, or produced scientifically correct answers.

## Technical call interface

Call the pure offline function:

    audit_calibration_transport(report, ledger, expected_model="glm-5.3", expected_route="coding", max_tokens=512)

Use CalibrationReport.to_dict() and the corresponding same-process PhysicalSendLedger.to_dict() as inputs. The function performs no network access or credential reads.

Regression tests:

    pytest -q tests/test_c3r_g1_calibration_audit.py tests/test_c3r_g1_multischema_calibration.py

These tests use fake transport responses with no actual Z.AI calls.

## Important provenance limitation

The physical reservation digest authenticates only the **request body relative to its local reconstruction**. The v0.1 ledger does not bind its HTTPS destination, provider request ID, independent backend timestamp or vendor invoice. Consequently expected_route is validated as a reviewed argument but **cannot be verified against the ledger entries**. All counts and HTTP statuses remain *self-reported* by the local process, not provider-authenticated. Any future change to request construction must update this auditor and its regression tests before live operation.

## Separate approval gate for live work

Before any actual provider send: review Z.AI plan/endpoint entitlement; freeze generation settings and calibration inputs before exposure; enforce a global provider-side request/monetary ceiling independent of Python process restarts; record request IDs and reconcile backend sends/invoice; obtain prior external witness/custodian authorization; and keep calibration outputs distinct from powered G1 evidence.

A synthetic 8/8 response formatting success does **not** authorize 480 paid sends or demonstrate acquired experience. No main merge, G1/G2/G3/G4 claim, historical evidence edit, or Pattern Register change occurs in v0.7.
