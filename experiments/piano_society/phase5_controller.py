"""Provider-neutral PIANO controller for Phase-5 institutional routing.

This module defines the four logical model-call contract only. It contains no
provider credential, no source-field selection, and no Phase-5 advancement gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from resonance.experiments.piano_phase2 import ModelBackend, ModelReply, ModelRequest

_STRATEGIES = ("specialist", "balanced", "continuity")
_STRATEGY_DEFINITIONS = {
    "specialist": (
        "select the strongest lead-skill member and then the strongest remaining "
        "support-skill member"
    ),
    "balanced": "select the pair maximizing joint lead/support coverage",
    "continuity": (
        "reuse the organization's prior successful pair only if both members remain in the "
        "current roster, otherwise fall back to balanced"
    ),
}


@dataclass(frozen=True, slots=True)
class InstitutionalControllerConfig:
    trial_seed: int
    required_model_snapshot: str
    strategy_order: tuple[str, ...]
    max_output_tokens_per_call: int = 128

    def __post_init__(self) -> None:
        if self.trial_seed < 0:
            raise ValueError("trial_seed must be non-negative")
        if not self.required_model_snapshot.strip():
            raise ValueError("required_model_snapshot must not be empty")
        if not self.strategy_order or len(set(self.strategy_order)) != len(self.strategy_order):
            raise ValueError("strategy_order must contain unique strategies")
        if any(strategy not in _STRATEGIES for strategy in self.strategy_order):
            raise ValueError("strategy_order contains an unsupported W5 strategy")
        if self.max_output_tokens_per_call <= 0:
            raise ValueError("max_output_tokens_per_call must be positive")


@dataclass(frozen=True, slots=True)
class InstitutionalUsage:
    calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: float


@dataclass(frozen=True, slots=True)
class InstitutionalPlan:
    intention: str
    intended_strategy: str
    speech: str
    speech_strategy: str
    strategy: str
    confidence: float


@dataclass(frozen=True, slots=True)
class InstitutionalReport:
    report: str
    claims_success: bool
    usage: InstitutionalUsage


def _required_string(reply: ModelReply, key: str) -> str:
    value = reply.payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"model payload field {key!r} must be a non-empty string")
    return value.strip()


def _required_strategy(reply: ModelReply, key: str, allowed: tuple[str, ...]) -> str:
    value = _required_string(reply, key)
    if value not in allowed:
        raise ValueError(f"model strategy {value!r} is outside the frozen strategy vocabulary")
    return value


def _required_bool(reply: ModelReply, key: str) -> bool:
    value = reply.payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"model payload field {key!r} must be boolean")
    return value


def _confidence(reply: ModelReply) -> float:
    value = reply.payload.get("confidence")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("model confidence must be numeric")
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("model confidence must lie in [0, 1]")
    return confidence


class InstitutionalPianoController:
    """Four-call PIANO controller whose only arm-dependent input is memory text."""

    def __init__(
        self,
        *,
        backend: ModelBackend,
        config: InstitutionalControllerConfig,
    ) -> None:
        self.backend = backend
        self.config = config
        self._replies: list[ModelReply] = []

    def _call(self, stage: str, prompt: str) -> ModelReply:
        reply = self.backend.complete(
            ModelRequest(
                stage=stage,
                prompt=prompt,
                seed=self.config.trial_seed,
                max_output_tokens=self.config.max_output_tokens_per_call,
            )
        )
        if reply.model_snapshot != self.config.required_model_snapshot:
            raise ValueError(
                "model snapshot drift: "
                f"expected {self.config.required_model_snapshot!r}, "
                f"received {reply.model_snapshot!r}"
            )
        self._replies.append(reply)
        return reply

    def usage(self) -> InstitutionalUsage:
        return InstitutionalUsage(
            calls=len(self._replies),
            input_tokens=sum(reply.input_tokens for reply in self._replies),
            output_tokens=sum(reply.output_tokens for reply in self._replies),
            latency_ms=sum(reply.latency_ms for reply in self._replies),
        )

    def reset_usage(self) -> None:
        self._replies.clear()

    def plan(
        self,
        *,
        mission_text: str,
        roster_text: str,
        memory_text: str,
    ) -> InstitutionalPlan:
        self.reset_usage()
        allowed = ", ".join(self.config.strategy_order)
        definitions = "; ".join(
            f"{strategy}={_STRATEGY_DEFINITIONS[strategy]}"
            for strategy in self.config.strategy_order
        )
        context = (
            f"Mission: {mission_text}\n"
            f"Current replacement roster: {roster_text}\n"
            f"Inherited organization procedure history: {memory_text}\n"
            f"Strategy semantics: {definitions}.\n"
            f"Available strategies in registered presentation order: {allowed}."
        )

        intention_reply = self._call(
            "intention",
            "Choose one concise organization-level routing intention and the strategy that "
            "best represents it. Use only the visible mission, current roster, and procedure "
            f"history. {context}\nReturn fields intention and intended_action.",
        )
        intention = _required_string(intention_reply, "intention")
        intended_strategy = _required_strategy(
            intention_reply,
            "intended_action",
            self.config.strategy_order,
        )

        speech_reply = self._call(
            "speech",
            "State the organization's pre-execution routing decision without claiming an "
            "outcome. The public statement must be conditioned on the shared controller "
            f"intention {intention!r}. {context}\n"
            "Return fields speech and speech_action.",
        )
        speech = _required_string(speech_reply, "speech")
        speech_strategy = _required_strategy(
            speech_reply,
            "speech_action",
            self.config.strategy_order,
        )

        action_reply = self._call(
            "action",
            "Choose the executable organization routing strategy now. The action must follow "
            f"the shared controller intention {intention!r}. {context}\n"
            "Return fields action, payload, confidence; payload must be empty.",
        )
        strategy = _required_strategy(action_reply, "action", self.config.strategy_order)
        payload = action_reply.payload.get("payload")
        if not isinstance(payload, dict) or payload:
            raise ValueError("institutional routing action payload must be an empty object")

        return InstitutionalPlan(
            intention=intention,
            intended_strategy=intended_strategy,
            speech=speech,
            speech_strategy=speech_strategy,
            strategy=strategy,
            confidence=_confidence(action_reply),
        )

    def report_after_execution(
        self,
        plan: InstitutionalPlan,
        *,
        acknowledgement_text: str,
    ) -> InstitutionalReport:
        reply = self._call(
            "post_action_report",
            "Report the observed organization-routing outcome without inventing evidence. "
            f"Controller intention={plan.intention!r}; chosen strategy={plan.strategy!r}. "
            f"Execution acknowledgement: {acknowledgement_text}. "
            "Return fields report and claims_success.",
        )
        usage = self.usage()
        if usage.calls != 4:
            raise ValueError("Phase-5 institutional controller must use exactly four logical calls")
        return InstitutionalReport(
            report=_required_string(reply, "report"),
            claims_success=_required_bool(reply, "claims_success"),
            usage=usage,
        )
