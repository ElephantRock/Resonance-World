from __future__ import annotations

import pytest

from resonance_world.authority import AuthorityGrant, AuthorityLedger


def test_authority_ledger_requires_exact_registered_record() -> None:
    ledger = AuthorityLedger()
    grant = AuthorityGrant(
        organization_id="org-opaque",
        scenario_id="scenario-opaque",
        action="ACT",
        notice_id="notice-0123456789abcdef01234567",
    )
    digest = ledger.register(grant)
    accepted = ledger.verify(
        notice_id=grant.notice_id,
        organization_id=grant.organization_id,
        scenario_id=grant.scenario_id,
        action=grant.action,
    )
    assert accepted.verified is True
    assert accepted.registered_grant_digest == digest

    mismatch = ledger.verify(
        notice_id=grant.notice_id,
        organization_id=grant.organization_id,
        scenario_id=grant.scenario_id,
        action="OTHER",
    )
    assert mismatch.verified is False
    assert mismatch.registered_grant_digest == digest

    unknown = ledger.verify(
        notice_id="notice-fedcba9876543210fedcba98",
        organization_id=grant.organization_id,
        scenario_id=grant.scenario_id,
        action=grant.action,
    )
    assert unknown.verified is False
    assert unknown.registered_grant_digest is None


def test_authority_notice_cannot_be_rebound() -> None:
    ledger = AuthorityLedger()
    ledger.register(AuthorityGrant("org", "scenario", "ACT", "notice"))
    with pytest.raises(ValueError, match="cannot be rebound"):
        ledger.register(AuthorityGrant("org", "scenario", "OTHER", "notice"))
