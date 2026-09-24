# D2-vNext-Q3-D construction status

**Tracking:** #296  
**Mode:** construction only  
**Provider/model execution:** **NOT AUTHORIZED**

Q3-D is a diagnostic successor to the consumed Q2-A stream. Its purpose is to localize the first structural disappearance or rejection of terminal assistant content across the provider → Hermes → terminal-adapter → exact-parser chain while preserving Q2 behavior.

## Frozen construction invariants in this revision

- no Q2-A rerun, rescue, replenishment, or marker cycling;
- no Q2-B execution;
- no new rescue mechanism, parser relaxation, prompt/task change, fallback, third invocation, tools, memory, session, or unregistered HTTP path;
- no raw prompt, provider response, assistant content, or retry content retained;
- structural enums, counts, lengths, token accounting when returned, and SHA-256 content commitments only;
- no provider-triggering workflow or execution marker is created by this construction revision;
- future Q3-D execution requires a separately frozen exact candidate, fresh cohort/sample plan, explicit physical-send ceiling, and separate explicit human authorization.

The machine-readable contract is `D2_VNEXT_Q3D_CONTRACT.json`; the structural record schema is `D2_VNEXT_Q3D_OBSERVABILITY_SCHEMA.json`.
