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

```json
{
  "action": "frozen-unauthorized",
  "manifest_digest": "c843f5042589559becb7510871d13d91f7a1337a43f051b76be25d5fdb8f27b8",
  "code_commit": "9919c9bcef5d3475b92f315f04f99a7dd85bba10",
  "status": "frozen-unauthorized",
  "contract_digest": "4f865ef204c2cedc71710b1549706e4970f53c595da48b40c62f4349b190a10a",
  "rules_version": "g1-v9-rules-v2",
  "recorded_at": "2026-10-25T16:48:57.901086+00:00",
  "recorded_by": "DSH agent on feature/g1-v9-integration (attested by independent reviewer on PR #312)"
}
```

Final `frozen-unauthorized` emission of the G1 v9 scientific freeze.
Manifest artifact:
`research/g1_v9/freeze-manifest-frozen-unauthorized.json` (committed in
the follow-up commit). Strict anchor verification passed against code
commit `9919c9b` via git-show blob comparison; provider authorization
remains false and the send cap remains zero. Also anchored externally
as a timestamped comment on PR #312.

## Annex A — Protocol values pinned final (PR #312 freeze review)

Decided by the independent reviewer in the freeze acceptance of
manifest `c843f5042589559becb7510871d13d91f7a1337a43f051b76be25d5fdb8f
27b8`:

1. **Practical-effect threshold: 20 percentage points — FINAL.** The
   manifest field `practical_threshold_status:
   proposed-pending-freeze` is superseded by this annex; the threshold
   is no longer merely proposed.
2. **Minimum analyzable worlds: 18 — FINAL.** The corresponding
   proposed status in the freeze documentation is superseded.

Both values now govern the G1 v9 scientific gate. **Changing either
one requires a new freeze record with a new manifest digest** under
the post-freeze change rule; the emitted manifest `c843f504…` is not
modified in place.
