elf.agent_a,
            "agent_b": self.agent_b,
            "episodes": [
                {
                    "mission_id": item.mission_id,
                    "context": item.context,
                    "agent_a": item.agent_a,
                    "action_a": item.action_a,
                    "agent_b": item.agent_b,
                    "action_b": item.action_b,
                    "success": item.success,
                }
                for item in self.episodes
            ],
        }


@dataclass(slots=True)
class RelationshipStateStore:
    """Persistent pair/partner state that intentionally excludes individual practice."""

    partner_models: dict[tuple[str, str], PartnerModel] = field(default_factory=dict)
    pair_memories: dict[tuple[str, str], SharedPairMemory] = field(default_factory=dict)

    def partner_model(self, owner: str, partner: str) -> PartnerModel:
        key = (owner, partner)
        if key not in self.partner_models:
            self.partner_models[key] = PartnerModel(owner, partner)
        return self.partner_models[key]

    def pair_memory(self, first: str, second: str) -> SharedPairMemory:
        key = _pair_key(first, second)
        if key not in self.pair_memories:
            self.pair_memories[key] = SharedPairMemory(*key)
        return self.pair_memories[key]

    def record(self, episode: JointEpisode) -> None:
        self.partner_model(episode.agent_a, episode.agent_b).observe(
            episode.context, episode.action_b
        )
        self.partner_model(episode.agent_b, episode.agent_a).observe(
            episode.context, episode.action_a
        )
        self.pair_memory(episode.agent_a, episode.agent_b).append(episode)

    def reset_partner_models(self, first: str, second: str) -> None:
        self.partner_models.pop((first, second), None)
        self.partner_models.pop((second, first), None)

    def clear_pair_memory(self, first: str, second: str) -> None:
        self.pair_memories.pop(_pair_key(first, second), None)

    def snapshot(self) -> dict[str, object]:
        models = [
            model.as_dict()
            for _, model in sorted(self.partner_models.items(), key=lambda item: item[0])
        ]
        memories = [
            memory.as_dict()
            for _, memory in sorted(self.pair_memories.items(), key=lambda item: item[0])
        ]
        value = {"pair_memories": memories, "partner_models": models}
        if "practice_by_skill" in json.dumps(value, sort_keys=True):
            raise AssertionError("individual practice leaked into relationship-state snapshot")
        return value


@dataclass(frozen=True, slots=True)
class JointEnvironment:
    """Pure outcome law with no relationship-state input."""

    base_success_probability: float = 0.35
    practice_gain: float = 0.16
    maximum_role_success: float = 0.94

    def __post_init__(self) -> None:
        if not 0 <= self.base_success_probability <= self.maximum_role_success <= 1:
            raise ValueError("invalid success probability bounds")
        if self.practice_gain < 0:
            raise ValueError("practice_gain must be non-negative")

    def role_probability(self, state: IndividualState, skill: str) -> float:
        return min(
            self.maximum_role_success,
            self.base_success_probability + self.practice_gain * math.sqrt(state.practice(skill)),
        )

    def evaluate(
        self,
        first: IndividualState,
        second: IndividualState,
        mission: JointMission,
        first_action: JointAction,
        second_action: JointAction,
        *,
        seed: int,
    ) -> bool:
        if first_action.agent_id != first.agent_id or second_action.agent_id != second.agent_id:
            raise ValueError("action identity does not match individual state")
        if first_action.role == second_action.role:
            return False

        role_state = {
            first_action.role: first,
            second_action.role: second,
        }
        lead_probability = self.role_probability(role_state["lead"], mission.lead_skill)
        support_probability = self.role_probability(role_state["support"], mission.support_skill)
        lead_ok = _uniform("w4a", mission.mission_id, seed, "lead") < lead_probability
        support_ok = _uniform("w4a", mission.mission_id, seed, "support") < support_probability
        return lead_ok and support_ok


@dataclass(frozen=True, slots=True)
class JointController:
    """Generic decision policy that may read learned relationship state."""

    def preferred_role(self, state: IndividualState, mission: JointMission) -> Role:
        lead = state.practice(mission.lead_skill)
        support = state.practice(mission.support_skill)
        if lead != support:
            return "lead" if lead > support else "support"
        return "lead" if _uniform("w4a-role", state.agent_id, mission.context) < 0.5 else "support"

    def choose_action(
        self,
        state: IndividualState,
        partner: IndividualState,
        mission: JointMission,
        relationships: RelationshipStateStore,
        communication: CommunicationPolicy,
        *,
        partner_message: Role | None = None,
    ) -> JointAction:
        preferred = self.preferred_role(state, mission)
        memory = relationships.pair_memory(state.agent_id, partner.agent_id)
        prior = memory.last_for_context(mission.context)

        if prior is not None:
            own_prior = prior.role_for(state.agent_id)
            partner_prior = prior.role_for(partner.agent_id)
            if prior.success:
                return JointAction(state.agent_id, own_prior)
            if own_prior == partner_prior:
                role = own_prior if state.agent_id < partner.agent_id else _other(own_prior)
                return JointAction(state.agent_id, role)

        prediction = relationships.partner_model(state.agent_id, partner.agent_id).predict(
            mission.context
        )
        if prediction == preferred:
            role = preferred if state.agent_id < partner.agent_id else _other(preferred)
            return JointAction(state.agent_id, role)

        if communication.bandwidth_bits >= 1 and partner_message == preferred:
            role = preferred if state.agent_id < partner.agent_id else _other(preferred)
            return JointAction(state.agent_id, role)

        return JointAction(state.agent_id, preferred)


@dataclass(slots=True)
class JointLearningSession:
    environment: JointEnvironment
    controller: JointController
    relationships: RelationshipStateStore
    communication: CommunicationPolicy

    def run_episode(
        self,
        first: IndividualState,
        second: IndividualState,
        mission: JointMission,
        *,
        seed: int,
    ) -> JointEpisode:
        first_message = self.controller.preferred_role(first, mission)
        second_message = self.controller.preferred_role(second, mission)
        first_action = self.controller.choose_action(
            first,
            second,
            mission,
            self.relationships,
            self.communication,
            partner_message=second_message,
        )
        second_action = self.controller.choose_action(
            second,
            first,
            mission,
            self.relationships,
            self.communication,
            partner_message=first_message,
        )
        success = self.environment.evaluate(
            first,
            second,
            mission,
            first_action,
            second_action,
            seed=seed,
        )
        episode = JointEpisode(
            mission_id=mission.mission_id,
            context=mission.context,
            agent_a=first.agent_id,
            action_a=first_action.role,
            agent_b=second.agent_id,
            action_b=second_action.role,
            success=success,
        )
        self.relationships.record(episode)
        return episode
