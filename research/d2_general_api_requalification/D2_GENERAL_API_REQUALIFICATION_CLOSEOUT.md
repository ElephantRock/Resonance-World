# D2 General API Hardened Transport Requalification — Closeout

## Outcome

The fresh engineering-only hardened General API requalification completed successfully under the explicitly authorized exact candidate `0e4ce60ef33c6a5f113ca6d0670501d48b3ed97e`.

Authoritative execution:

- authorization commit: `a9511695e225e5495e72272f31f9e34a52702556`;
- workflow: `34053215253`, attempt 1, SUCCESS;
- artifact: `9995184080`;
- artifact digest: `sha256:76d2b29e313f50cd109b8ea966a5872828f117bef64f1919d0ff911aeb02c1fb`;
- preserved result SHA-256: `e2bf6629fb9b0668f4a705153d106f5d762612912d634838900c21c1d4d7db81`.

## Qualification result

All three fixed no-retry probes passed the hardened transport contract:

- every probe initiated exactly one HTTPS attempt;
- redirects were disabled and zero redirects were followed;
- every probe returned HTTP 200;
- every probe returned exact model identity `glm-5-turbo`;
- the minimal text response was non-empty;
- the minimal JSON response was valid strict JSON;
- the D2-shaped JSON response contained exactly eight legal actions;
- response-body reading remained under the hardened absolute-deadline / incomplete-body rules.

Therefore:

- `redirect_history_verified = true`;
- `one_physical_request_per_probe_verified = true`;
- `qualification_pass = true`;
- `transport_qualified_for_future_prospective_design = true`.

## Historical boundary

This closeout does **not** rewrite or upgrade the historical issue #202 result. That earlier stream remains permanently bounded at `completed_response_level_pass_redirect_unverified`. The new requalification is separate fresh engineering evidence.

## Scientific boundary

This execution produced no scientific Field trajectory, no capability-acquisition score, no reproduction evidence, and no Mechanism Registry evidence. It does not authorize a scientific campaign.

The next eligible program step is construction and prospective freeze of a fresh source-capability-acquisition study using the now-qualified transport. External provider execution for that future scientific study requires a separate explicit authorization after its exact candidate is frozen.

Production/default Historical Substrate remains **OFF**.
