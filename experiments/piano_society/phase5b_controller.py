"""Four-call PIANO controller for Phase-5B transferable institutional memory."""

from __future__ import annotations

from dataclasses import dataclass

from resonance.experiments.piano_phase2 import ModelBackend, ModelReply, ModelRequest

_ALLOWED = ("specialist", "balanced")
_DEFINITIONS = {
    "specialist": (
        "select the strongest lead-skill member, then the strongest remaining support-skill member"
    ),
    "balanced": "select the pair maximizing joint coverage across both mission skills",
}


@dataclass(frozen=True, slots=True)
class TransferControllerConfig:
    trial_seed: int
    required_model_snapshot: str
    strategy_order: tuple[str, str]
    max_output_tokens_per_call: int = 128

    def __post_init__(self) -> None:
        if self.trial_seed < 0:
            raise ValueError("trial_seed must be non-negative")
        if not self.required_model_snapshot.strip():
            raise ValueError("required_model_snapshot must not be empty")
        if len(self.strategy_order) != 2 or set(self.strategy_order) != set(_ALLOWED):
            raise ValueError("strategy_order must be a permutation of the binary routing strategies")
        if self.max_output_tokens_per_call <= 0:
            raise ValueError("max_output_tokens_per_call must be positive")


@dataclass(frozen=True, slots=True)
class TransferPlan:
    intention: str
    intended_strategy: str
    speech: str
    speech_strategy: str
    strategy: str
    confidence: float


@dataclass(frozen=True, slots=True)
class TransferUsage:
    calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: float


@dataclass(frozen=True, slots=True)
class TransferReport:
    report: str
    claims_success: bool
    usage: TransferUsage


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
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ValueError("model confidence must lie in [0, 1]")
    return result


class TransferableInstitutionalController:
    """PIANO decision bottleneck over an institution-owned structural forecast."""

    def __init__(self, *, backend: ModelBackend, config: TransferControllerConfig) -> None:
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

    def reset_usage(self) -> None:
        self._replies.clear()

    def usage(self) -> TransferUsage:
        return TransferUsage(
            calls=len(self._replies),
            input_tokens=sum(reply.input_tokens for reply in self._replies),
            output_tokens=sum(reply.output_tokens for reply in self._replies),
            latency_ms=sum(reply.latency_ms for reply in self._replies),
        )

    def plan(self, *, mission_text: str, roster_text: str, memory_text: str) -> TransferPlan:
        self.reset_usage()
        allowed = ", ".join(self.config.strategy_order)
        definitions = "; ".join(
            f"{strategy}={_DEFINITIONS[strategy]}" for strategy in self.config.strategy_order
        )
        context = (
            f"Mission: {mission_text}\n"
            f"Current replacement roster: {roster_text}\n"
            f"Inherited institutional model memory: {memory_text}\n"
            f"Routing semantics: {definitions}.\n"
            f"Available strategies in registered presentation order: {allowed}."
        )
        evidence_rule = (
            "The memory's current_roster_strategy_forecast is organization-owned predictive "
            "evidence computed from prior episodes plus the current roster. It is not an observed "
            "outcome or a guarantee. Prefer the routing strategy with the stronger supported "
            "forecast unless the supplied evidence itself gives a concrete reason not to."
        )

        intention_reply = self._call(
            "intention",
            "Choose one concise organization-level routing intention and its strategy. "
            f"{evidence_rule} {context}\nReturn fields intention and intended_action.",
        )
        intention = _required_string(intention_reply, "intention")
        intended_strategy = _required_strategy(
            intention_reply, "intended_action", self.config.strategy_order
        )

        speech_reply = self._call(
            "speech",
            "State the organization's pre-execution routing decision without claiming an outcome. "
            f"Condition the statement on the shared controller intention {intention!r}. "
            f"{evidence_rule} {context}\nReturn fields speech and speech_action.",
        )
        speech = _required_string(speech_reply, "speech")
        speech_strategy = _required_strategy(
            speech_reply, "speech_action", self.config.strategy_order
        )

        action_reply = self._call(
            "action",
            "Choose the executable organization routing strategy now. "
            f"Follow the shared controller intention {intention!r}. {evidence_rule} {context}\n"
            "Return fields action, payload, confidence; payload must be empty.",
        )
        strategy = _required_strategy(action_reply, "action", self.config.strategy_order)
        payload = action_reply.payload.get("payload")
        if not isinstance(payload, dict) or payload:
            raise ValueError("Phase-5B routing action payload must be an empty object")

        return TransferPlan(
            intention=intention,
            intended_strategy=intended_strategy,
            speech=speech,
            speech_strategy=speech_strategy,
            strategy=strategy,
            confidence=_confidence(action_reply),
        )

    def report_after_execution(
        self, plan: TransferPlan, *, acknowledgement_text: str
    ) -> TransferReport:
        reply = self._call(
            "post_action_report",
            "Report the observed organization-routing outcome without inventing evidence. "
            f"Controller intention={plan.intention!r}; chosen strategy={plan.strategy!r}. "
            f"Execution acknowledgement: {acknowledgement_text}. "
            "Return fields report and claims_success.",
        )
        usage = self.usage()
        if usage.calls != 4:
            raise ValueError("Phase-5B controller must use exactly four logical calls")
        return TransferReport(
            report=_required_string(reply, "report"),
            claims_success=_required_bool(reply, "claims_success"),
            usage=usage,
        )
