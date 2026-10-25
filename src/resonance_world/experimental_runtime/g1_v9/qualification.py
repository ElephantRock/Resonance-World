"""Qualification Authorization Candidate for the first provider contact.

Separate from the scientific freeze: this module defines the small,
cost-capped qualification run that verifies the transport and
accounting layer **before** any full-world execution is proposed.

Design (per the freeze review):

- default mode is **dry**: the transport records would-be sends and
  performs no network I/O whatsoever;
- a real ``SendMeter`` enforces the send cap fail-closed - the send is
  refused *before* it would occur and the refusal is recorded;
- the proposed authorization, if granted later, is a **small explicit
  cap** (8 physical sends) for a connectivity-and-format probe - not a
  full world (420 sends) and not the 24-world campaign;
- auto-stop: every send path checks the meter first, so reaching the
  cap stops execution automatically;
- pre-flight failure classes are enumerated and must each be exercised
  in dry mode before any live qualification.

Nothing in this module contains credentials, endpoints, or network
code. ``authorized`` is false until a separate explicit human
authorization names the code commit, provider, model, and cap.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .call_contract import ENDPOINT_FAMILY, MODEL, PROVIDER, RUNTIME_SPEC
from .contract import G1V9Contract, default_contract
from .send_ledger import PhysicalSendCapExceeded  # re-exported
from .zai_transport import (
    SCIENCE_ANCHOR_DIGEST,
    QualificationAuthorizationRecord,
)

QUALIFICATION_SCHEMA = "g1-v9-qualification-plan-v1"

#: The small, explicit cap proposed for the connectivity probe.
PROPOSED_QUALIFICATION_SEND_CAP = 8


@dataclass(frozen=True, slots=True)
class SendRecord:
    """One metered send reservation (label and canonical payload digest)."""

    index: int
    label: str
    payload_sha256: str


class SendMeter:
    """A fail-closed physical-send meter with a hard cap.

    ``reserve`` is called immediately before any physical send would
    occur. When the cap is exhausted it raises
    :class:`PhysicalSendCapExceeded` **without** recording a send, so
    the meter's count is always the exact number of sends that were
    actually permitted.
    """

    def __init__(self, max_sends: int) -> None:
        if isinstance(max_sends, bool) or not isinstance(max_sends, int) or max_sends <= 0:
            raise ValueError("max_sends must be a positive integer")
        self._max_sends = max_sends
        self._records: list[SendRecord] = []
        self.refused = 0

    @property
    def max_sends(self) -> int:
        return self._max_sends

    @property
    def used(self) -> int:
        return len(self._records)

    @property
    def remaining(self) -> int:
        return self._max_sends - len(self._records)

    def reserve(self, label: str, payload_sha256: str) -> SendRecord:
        """Reserve one physical send or raise fail-closed."""

        if len(self._records) >= self._max_sends:
            self.refused += 1
            raise PhysicalSendCapExceeded(
                f"send cap exhausted ({self._max_sends} sends); "
                "auto-stop: refusing further sends"
            )
        record = SendRecord(
            index=len(self._records) + 1,
            label=label,
            payload_sha256=payload_sha256,
        )
        self._records.append(record)
        return record

    def records(self) -> tuple[SendRecord, ...]:
        """Return the permitted send records in order."""

        return tuple(self._records)


@dataclass(frozen=True, slots=True)
class DryRunTransport:
    """A recording transport that performs no network I/O.

    Every send goes through the meter first; refused sends raise before
    anything is recorded. Accepted sends are journaled with their
    payload digest and answered with a fixed dry-run acknowledgement.
    """

    meter: SendMeter
    journal: tuple[tuple[str, str], ...] = field(default=())

    def send(self, label: str, payload: dict[str, str]) -> str:
        from resonance_world.adapters import sha256_json

        self.meter.reserve(label, payload_sha256=sha256_json(payload))
        object.__setattr__(
            self,
            "journal",
            self.journal + ((label, sha256_json(payload)),),
        )
        return "dry-run-ack"


def preflight_failure_classes() -> tuple[str, ...]:
    """Return the failure classes the qualification must exercise dry."""

    return tuple(
        sorted(
            (
                "auth-failure",
                "timeout",
                "malformed-response",
                "send-cap-exceeded",
            )
        )
    )


@dataclass(frozen=True, slots=True)
class QualificationPlan:
    """The qualification authorization candidate (dry by default)."""

    schema: str
    provider: str
    model: str
    endpoint_family: str
    runtime_spec: str
    world_count: int
    full_world_model_sends: int
    proposed_send_cap: int
    cap_scope: str
    dry_run: bool
    auto_stop_at_cap: bool
    authorized: bool
    preflight_failure_classes: tuple[str, ...]
    contract_digest: str
    notes: tuple[str, ...]


def build_qualification_plan(
    contract: G1V9Contract | None = None,
) -> QualificationPlan:
    """Build the qualification authorization candidate (dry, unauthorized)."""

    contract = contract or default_contract()
    from .call_contract import budget_summary

    budget = budget_summary(contract)
    return QualificationPlan(
        schema=QUALIFICATION_SCHEMA,
        provider=PROVIDER,
        model=MODEL,
        endpoint_family=ENDPOINT_FAMILY,
        runtime_spec=RUNTIME_SPEC,
        world_count=1,
        full_world_model_sends=budget["model_sends_per_world"],
        proposed_send_cap=PROPOSED_QUALIFICATION_SEND_CAP,
        cap_scope="connectivity-and-format-probe",
        dry_run=True,
        auto_stop_at_cap=True,
        authorized=False,
        preflight_failure_classes=sorted(preflight_failure_classes()),
        contract_digest=contract.digest(),
        notes=(
            "this candidate authorizes nothing; a live qualification run "
            "requires a separate explicit authorization naming the code "
            "commit, provider, model, and the small send cap",
            "arm D is computational and never generates provider sends",
            "the full-world 420-send budget is NOT proposed here",
        ),
    )


def build_authorization_candidate(
    *,
    code_commit: str,
    endpoint_url: str,
    max_output_tokens: int = 512,
    timeout_seconds: float = 30.0,
    contract: G1V9Contract | None = None,
) -> QualificationAuthorizationRecord:
    """Build the UNAUTHORIZED candidate authorization record (dry).

    The candidate is bound to the frozen science anchor and carries the
    pinned operational values, plus a unique ``authorization_id``
    derived from the science anchor and the operational commit. It is
    emitted with ``authorized=False`` and ``status=
    candidate-awaiting-independent-authorization``: it cannot enable the
    transport. Only an independent human authorization record with
    ``authorized=True`` can.
    """

    contract = contract or default_contract()
    authorization_id = hashlib.sha256(
        f"{SCIENCE_ANCHOR_DIGEST}:{code_commit}".encode()
    ).hexdigest()
    return QualificationAuthorizationRecord(
        schema="g1-v9-qualification-authorization-v1",
        status="candidate-awaiting-independent-authorization",
        science_anchor_digest=SCIENCE_ANCHOR_DIGEST,
        code_commit=code_commit,
        authorization_id=authorization_id,
        provider=PROVIDER,
        model=MODEL,
        endpoint_family=ENDPOINT_FAMILY,
        endpoint_url=endpoint_url,
        send_cap=PROPOSED_QUALIFICATION_SEND_CAP,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        authorized=False,
        authorized_by="",
        authorized_at="",
        notes=(
            "candidate record: dry; enabling the transport requires an "
            "independent authorization with authorized=true naming this "
            "authorization_id"
        ),
    )
