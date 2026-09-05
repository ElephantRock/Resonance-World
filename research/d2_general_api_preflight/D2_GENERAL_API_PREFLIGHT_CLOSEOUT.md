# D2 General API preflight closeout

The bounded General API engineering preflight completed under frozen candidate
`2d3f46ad381fbe9d5da069239f0ab3e7ef2d678f` and sole-child authorization commit
`c1b10dcfab8fae38fb276adcd3199c978d0d5662`.

Authoritative execution was workflow `33992155068`, attempt 1. Authorization integrity and
the bounded execution job both succeeded; the rerun-prohibited job was skipped because this
was the first and only attempt.

All three preserved final responses were HTTP 200 and reported exact returned model identity
`glm-5-turbo`. The minimal JSON probe returned non-empty valid JSON. The D2-shaped probe
returned non-empty valid JSON with the required 8-action shape. The preserved historical
result therefore reports `qualification_pass: true` under the evaluator that executed with
that stream.

Post-execution review established an important claim limitation: the executed client used the
default redirect-following `urllib` opener and the preserved artifact does not record redirect
history. The historical run therefore does **not** establish that each logical probe corresponded
to exactly one physical HTTP request, and it does **not** fully qualify the General API transport
for a future prospective scientific design. Its closeout status is
`completed_response_level_pass_redirect_unverified`. A fresh prospective engineering
requalification is required using the hardened no-redirect transport before scientific use.

This remains engineering evidence only. It does not reinterpret D2d, replace any failed D2d
data, establish source capability acquisition, authorize a scientific campaign, change the
Mechanism Registry, or enable Historical Substrate.

The exact historical result is preserved in
`research/d2_general_api_preflight/evidence/d2-general-api-preflight-result.json` and is bound
to workflow artifact `9976954042`, digest
`sha256:4ce006afc0397847709f41100a291ae5ccf2a2637096afe15589e85e9e1ae665`, with result-file
SHA-256 `607994b0e3679fa65ec89150cf58d09b1e560156dcf8009af499463004082a2f`.

Post-execution apparatus maintenance now rejects redirects, requires explicit HTTP 200 for
qualification, records connection timeouts, and bounds response-body read failures so a
truncated or stalled body becomes a failed diagnostic row instead of aborting the remaining
probe stream. These changes are prospective and do not retroactively change the historical
execution.

Any fresh engineering requalification requires a new prospective stream, freeze, and separate
exact-candidate execution authorization. Any future source-acquisition study must then be a
separate prospective scientific stream with a fresh design, freeze, cohort/request
materialization, and separate exact-candidate execution authorization. Production/default
Historical Substrate remains OFF.
