# C3R G1 — Host-Persistent Calibration Send Budget v0.8

**Classification: offline engineering safety control, not a provider-side money or send limit, not independent custody, not approval for a live G1 trial.**

The output calibration transport in v0.7 used an in-process ledger with at most eight reservations. Starting another Python interpreter resets such a counter. v0.8 introduces an **optional host-local campaign reservation file** that is synchronized with Linux fcntl.flock and flushed with fsync **before** a provider transport could be called.

## Implemented files and integration

- src/resonance_world/c3r_g1_host_campaign_budget.py — `HostCampaignBudget`: exclusive-create precommitment, locked read/validate/reserve, chained reservation SHA256 hashes, persistent monotonic ordinal and strict campaign/endpoint/request sequence, offline inspect and initialize CLI.
- src/resonance_world/c3r_g1_zai_transport.py — optional `campaign_budget` on `ZaiStandardModelPort`; when supplied, every call MUST obtain the persistent reservation before its existing per-process reservation and before its injected HTTPS transport. A mismatch or depleted cap opens the port's circuit and prevents dispatch. Existing historical transport behavior without this optional guard is left compatible.
- tests/test_c3r_g1_host_campaign_budget.py — exact eight locked request digests from prospective two-schema calibration, cross-object restart, actual Python child-process reuse, concurrent requests competing for one slot, OS mode/symlink/hardlink and file corruption checks, wrong endpoint/budget/sequence, no refill after failure, disabled-by-default dispatch, and mocked transport integration.

The initial file must be in an already-existing private 0700 directory owned by the process UID. Its own mode must be 0600, link count exactly one, and it must not be a symlink. A single exclusive-create file binds a unique campaign ID, one hard-pinned Z.AI standard/coding endpoint, the chosen maximum (1–8), and the exact eight SHA256 hashes of the **canonical request bodies**, in order. Every reservation consumes a nonrefundable slot even if the process crashes or the network fails. The program serializes competitors with flock, validates all preceding events and headers, fsyncs the new reservation before returning, and refuses a ninth claim.

**Identical request SHA256 values are permitted** when blinded calibration arms intentionally receive byte-identical prompts. The ordinal, not hash uniqueness, defines the next slot. This budget prevents accidental extra sends, but request-body equality does **not** independently attest the arm identity or that a model response was associated with the correct logical arm.

## Offline operator commands (zero network activity)

Create a private existing parent directory as the intended process UID; choose one campaign ID that is not reused.

    python -m resonance_world.c3r_g1_host_campaign_budget initialize --path /private/g1-budget/campaign.json --campaign-id g1-calibration-run-001 --route coding --model glm-5.3 --max-tokens 512 --maximum 8

Read without consuming slots:

    python -m resonance_world.c3r_g1_host_campaign_budget inspect --path /private/g1-budget/campaign.json --campaign-id g1-calibration-run-001 --route coding --model glm-5.3 --max-tokens 512 --maximum 8

The CLI provides NO live send command and requires NO Z.AI API key. It cannot silently reset an existing file with initialize; exit code 2 indicates rejection. Use the reviewed code/API to pass a `HostCampaignBudget` to an opt-in `ZaiStandardModelPort`; nothing in the offline CLI itself enables the provider port.

Tests:

    pytest -q tests/test_c3r_g1_host_campaign_budget.py tests/test_c3r_g1_calibration_audit.py

## What this does and does NOT protect

**Under a single trusted Linux host account and its private directory**, the quota survives process restart, serializes interprocess contention, binds all claimed requests to one endpoint and frozen request-body schedule, and burns reservations even for ambiguous outcomes. It does not support retry, automatic restoration, cross-host consensus or campaign resumption after failed/unfinished requests. A corrupted/truncated state fails closed until independently investigated — never erase the file to recover a slot.

**This is not a global provider limit.** A privileged/local file owner can copy, replace or rewrite a coherent history (the SHA256 chain is **not** independently signed), and a malicious operator could select another path, host, credential or campaign ID to escape this *optional* guard. Container restarts without a **persistent mounted volume** also lose it. The upstream Z.AI billing system, endpoint entitlements and real invoices are still independent facts. No actual hard-money cap can be inferred from eight requests: prompt tokens, completion tokens, provider pricing and retry behavior matter. Hard spending caps and provider-side request IDs must be established and checked out-of-band. Backend records are not attached here.

**Scientific/authority gate:** this protects an engineering calibration apparatus only. It does not supply graded feedback, hidden-target truth, placebo validity, independent learner units, powered acquisition evidence, a real third-party witness, WORM storage or authorization for paid calls. A local Python file does not solve scientific or provider provenance. Remain at G1 **untested** for the prospective multischema model campaign, leave old 16/512-token diagnostics frozen, keep draft PR #310 open, and do not promote G2/G3/G4 or Pattern Register entries.
