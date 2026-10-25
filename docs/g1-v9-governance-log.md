# G1 v9 — Governance Log (append-only)

This log is the independent governance record for G1 v9 freeze anchors.
Every freeze-relevant action appends one entry here; entries are never
edited or removed. The log lives outside the manifest file itself, so
the recorded manifest digest can always be checked against the manifest
content independently.

Entry format (one JSON object per entry):

```json
{
  "action": "candidate-emitted | frozen-unauthorized | authorized | executed | closed",
  "manifest_digest": "<sha256 of the manifest content>",
  "code_commit": "<40-hex commit the manifest pins>",
  "status": "<manifest status>",
  "contract_digest": "<contract digest>",
  "rules_version": "<rules version>",
  "recorded_at": "<ISO-8601 UTC>",
  "recorded_by": "<actor>"
}
```

## Entries

- `candidate-emitted` — manifest digest
  `bfd24e5919869cdd` (prefix; full digest in
  `research/g1_v9/freeze-manifest-candidate.json` at commit `0d3aa3a`),
  code commit `0d3aa3a` (working-tree candidate), status
  `candidate-pre-freeze`. Recorded by DSH, 2026-10-25.
