"""Default-off pure contract for bounded evidence access."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

HISTORICAL_ACCESS_DEFAULT_ENABLED = False


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def bounded_historical_evidence(
    records: Iterable[Mapping[str, Any]],
    *,
    query_id: str,
    requesting_organization_id: str,
    predicate: str,
    decision_cutoff: int,
    result_limit: int,
    enabled: bool = HISTORICAL_ACCESS_DEFAULT_ENABLED,
    evidence_release_commit: str,
) -> dict[str, Any]:
    if result_limit < 0:
        raise ValueError("result_limit must be nonnegative")
    if not enabled:
        return {
            "schema": "historical-access-denial-v0.1",
            "query_id": query_id,
            "status": "historical_access_disabled",
            "bundle": None,
        }
    selected = [
        dict(row)
        for row in records
        if str(row["organization_id"]) == requesting_organization_id
        and str(row["predicate"]) == predicate
        and int(row["observed_at"]) <= decision_cutoff
    ]
    selected.sort(key=lambda row: (int(row["observed_at"]), str(row["claim_id"])))
    selected = selected[:result_limit]
    base = {
        "schema": "historical-evidence-bundle-v0.1",
        "query_id": query_id,
        "requesting_organization_id": requesting_organization_id,
        "decision_cutoff": decision_cutoff,
        "scope": {"predicate": predicate},
        "result_limit": result_limit,
        "status": "empty" if not selected else "ok",
        "evidence": selected,
        "evidence_release_commit": evidence_release_commit,
    }
    return {
        **base,
        "bundle_id": "history-bundle-" + hashlib.sha256(_bytes(base)).hexdigest()[:24],
    }


__all__ = ["HISTORICAL_ACCESS_DEFAULT_ENABLED", "bounded_historical_evidence"]
