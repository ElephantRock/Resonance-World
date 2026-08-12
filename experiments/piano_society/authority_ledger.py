"""Minimal World-owned authority ledger for the PIANO Phase-4 experiment.

This is an experiment-local provenance primitive, not a production organization
API. It makes the authority intervention machine-verifiable: legitimate grants
are registered as canonical immutable records; conflicting unregistered notices
cannot pass verification merely because their text sounds authoritative.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

_LEDGER_SCHEMA = "resonance-world-authority-ledger-v0.1"
_GRANT_SCHEMA = "resonance-world-authority-grant-v0.1"


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    organization_id: str
    scenario_id: str
    action: str
    notice_id: str

    def canonical_record(self) -> dict[str, str]:
        return {
            "schema": _GRANT_SCHEMA,
            "organization_id": self.organization_id,
            "scenario_id": self.scenario_id,
            "action": self.action,
            "notice_id": self.notice_id,
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_record(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


class AuthorityLedger:
    """Immutable-by-key registry used to verify experimental authority grants."""

    schema = _LEDGER_SCHEMA

    def __init__(self) -> None:
        self._grants: dict[str, AuthorityGrant] = {}

    def register(self, grant: AuthorityGrant) -> str:
        if not grant.organization_id.strip() or not grant.scenario_id.strip():
            raise ValueError("authority grants require organization and scenario ids")
        if not grant.action.strip() or not grant.notice_id.strip():
            raise ValueError("authority grants require action and notice ids")
        existing = self._grants.get(grant.notice_id)
        if existing is not None and existing != grant:
            raise ValueError("authority notice id cannot be rebound")
        self._grants[grant.notice_id] = grant
        return grant.digest

    def verify(
        self,
        *,
        notice_id: str,
        organization_id: str,
        scenario_id: str,
        action: str,
    ) -> bool:
        grant = self._grants.get(notice_id)
        return grant == AuthorityGrant(
            organization_id=organization_id,
            scenario_id=scenario_id,
            action=action,
            notice_id=notice_id,
        )

    def digest_for(self, notice_id: str) -> str | None:
        grant = self._grants.get(notice_id)
        return None if grant is None else grant.digest
