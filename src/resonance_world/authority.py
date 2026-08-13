"""World-owned opaque institutional-authority verification.

This production primitive is narrowly extracted from the PIANO Phase-4C authority
ledger validated at World revision b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1.
Authority is an explicit registered World fact: text, historical evidence, and semantic
labels cannot make an unregistered notice authoritative.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

AUTHORITY_VALIDATION_WORLD_REVISION = "b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1"
AUTHORITY_VALIDATION_WORKFLOW_RUN = 31638087507

_LEDGER_SCHEMA = "resonance-world-authority-ledger-v0.1"
_GRANT_SCHEMA = "resonance-world-authority-grant-v0.1"
_VERIFICATION_SCHEMA = "resonance-world-authority-verification-v0.1"


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


@dataclass(frozen=True, slots=True)
class AuthorityVerification:
    notice_id: str
    organization_id: str
    scenario_id: str
    action: str
    verified: bool
    registered_grant_digest: str | None

    def canonical_record(self) -> dict[str, object]:
        return {
            "schema": _VERIFICATION_SCHEMA,
            "notice_id": self.notice_id,
            "organization_id": self.organization_id,
            "scenario_id": self.scenario_id,
            "action": self.action,
            "verified": self.verified,
            "registered_grant_digest": self.registered_grant_digest,
        }


class AuthorityLedger:
    """Immutable-by-notice World registry for explicit institutional authority."""

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
    ) -> AuthorityVerification:
        expected = AuthorityGrant(
            organization_id=organization_id,
            scenario_id=scenario_id,
            action=action,
            notice_id=notice_id,
        )
        registered = self._grants.get(notice_id)
        return AuthorityVerification(
            notice_id=notice_id,
            organization_id=organization_id,
            scenario_id=scenario_id,
            action=action,
            verified=registered == expected,
            registered_grant_digest=None if registered is None else registered.digest,
        )

    def digest_for(self, notice_id: str) -> str | None:
        grant = self._grants.get(notice_id)
        return None if grant is None else grant.digest


__all__ = [
    "AUTHORITY_VALIDATION_WORKFLOW_RUN",
    "AUTHORITY_VALIDATION_WORLD_REVISION",
    "AuthorityGrant",
    "AuthorityLedger",
    "AuthorityVerification",
]
