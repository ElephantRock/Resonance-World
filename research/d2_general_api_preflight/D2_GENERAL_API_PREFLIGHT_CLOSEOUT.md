# D2 General API preflight closeout

The bounded General API engineering preflight completed successfully under frozen candidate
`2d3f46ad381fbe9d5da069239f0ab3e7ef2d678f` and sole-child authorization commit
`c1b10dcfab8fae38fb276adcd3199c978d0d5662`.

Authoritative execution was workflow `33992155068`, attempt 1. Authorization integrity and
the bounded execution job both succeeded; the rerun-prohibited job was skipped because this
was the first and only attempt.

All three fixed requests returned HTTP 200 and exact returned model identity
`glm-5-turbo`. The minimal JSON probe returned non-empty valid JSON. The D2-shaped probe
returned non-empty valid JSON with the required 8-action shape. The result therefore reports
`qualification_pass: true`.

This is engineering transport evidence only. It establishes that, at preflight time, the
General API route satisfied the frozen three-probe contract. It does not reinterpret D2d,
replace any failed D2d data, establish source capability acquisition, authorize a scientific
campaign, change the Mechanism Registry, or enable Historical Substrate.

The exact result is preserved in
`research/d2_general_api_preflight/evidence/d2-general-api-preflight-result.json` and is bound
to workflow artifact `9976954042`, digest
`sha256:4ce006afc0397847709f41100a291ae5ccf2a2637096afe15589e85e9e1ae665`, with result-file
SHA-256 `607994b0e3679fa65ec89150cf58d09b1e560156dcf8009af499463004082a2f`.

Any future source-acquisition study must be a new prospective scientific stream with a fresh
design, freeze, cohort/request materialization, and separate exact-candidate execution
authorization. Production/default Historical Substrate remains OFF.
