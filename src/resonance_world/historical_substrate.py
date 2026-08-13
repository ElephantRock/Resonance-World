"""Default-off pure contract for bounded historical evidence access.

The module contains no ContextGraph integration and no World/Field outcome logic. It
accepts already-admissible evidence records explicitly and rejects forbidden consumers
before any evidence selection occurs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

HISTORICAL_ACCESS_DEFAULT_ENABLED = False
HISTORICAL_CONTROLLER_CONSUMER = "organization_controller"
HISTORICAL_FORBIDDEN_CONSUMERS = frozenset(
    {
        "contextgraph_to_world_outcome_law",
        "contextgraph_to_field_capability_state",
        "contextgraph_to_automatic_authority",
        "contextgraph_to_automatic_policy",
    }
)


class HistoricalAccessForbidden(PermissionError):
    """Fail-closed rejection of an unauthorized historical-evidence consumer."""

    code = "historical_access_forbidden_consumer"

    def __init__(self, consumer: str) -> None:
        self.consumer = consumer
        super().__init__(f"historical evidence consumer is forbidden: {consumer}")


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def require_historical_consumer(consumer: str) -> None:
    """Permit only the explicit organization-controller treatment consumer."""
    if consumer != HISTORICAL_CONTROLLER_CONSUMER:
        raise HistoricalAccessForbidden(consumer)


def bounded_historical_evidence(
    records: Iterable[Mapping[str, Any]],
    *,
    query_id: str,
    requesting_organization_id: str,
    predicate: str,
    decision_cutoff: int,
    result_limit: int,
    consumer: str = HISTORICAL_CONTROLLER_CONSUMER,
    enabled: bool = HISTORICAL_ACCESS_DEFAULT_ENABLED,
    evidence_release_commit: str,
) -> dict[str, Any]:
    """Return a bounded evidence bundle only to the registered controller consumer."""
    require_historical_consumer(consumer)
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


__all__ = [
    "HISTORICAL_ACCESS_DEFAULT_ENABLED",
    "HISTORICAL_CONTROLLER_CONSUMER",
    "HISTORICAL_FORBIDDEN_CONSUMERS",
    "HistoricalAccessForbidden",
    "bounded_historical_evidence",
    "require_historical_consumer",
]
