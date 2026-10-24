"""Agent-visible observations and the model decision boundary.

Nothing in this module can reach private evaluator state: observations
are built from the public state projection and the public event log
only. Model-generated decisions enter the world exclusively through
``DecisionRequest``/``record_decision`` flows that record the decision
as an external-input event; replay consumes the recorded event and
never invokes a port.

The ``ModelDecisionPort`` protocol is a default-off integration
contract, following the same constitutional pattern as the C3R G1
model boundary: the kernel ships no transport, no credentials, and no
provider access of any kind.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .events import WorldEvent
from .state import StateValue


@dataclass(frozen=True, slots=True)
class Observation:
    """The complete agent-visible view of the world at one moment."""

    scenario_id: str
    branch_id: str
    tick: int
    public_state: Mapping[str, StateValue]
    public_state_sha256: str
    new_events: tuple[WorldEvent, ...]


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """A recorded observation awaiting exactly one external decision."""

    request_id: str
    branch_id: str
    tick: int
    observation_seq: int
    observation: Observation


class ModelDecisionPort(Protocol):
    """A decision source injected by the caller.

    Implementations hold ``model_id`` provenance and return a decision as
    a canonical mapping of int/str values. The kernel never constructs a
    port, never imports a provider SDK, and replay never calls one.
    """

    model_id: str

    def decide(self, request: DecisionRequest) -> Mapping[str, Any]:
        """Return one decision for ``request``; must be side-effect free."""
        ...
