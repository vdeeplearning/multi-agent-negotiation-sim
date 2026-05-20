from app.providers.base import BaseLLMProvider
from app.schemas import AgentResponse, AgentRole, NegotiationConfig, Offer, TranscriptEntry


class NegotiationAgent:
    def __init__(self, role: AgentRole, provider: BaseLLMProvider) -> None:
        self.role = role
        self.provider = provider

    def act(
        self,
        config: NegotiationConfig,
        history: list[TranscriptEntry],
        latest_offer: Offer | None,
        round_number: int,
    ) -> AgentResponse:
        private_config = config.buyer if self.role == AgentRole.BUYER else config.seller
        payload = {
            "role": self.role,
            "private_config": private_config,
            "public_history": history,
            "latest_offer": latest_offer,
            "system_constraints": {
                "do_not_reveal_private_goals": True,
                "return_json_schema": "AgentResponse",
            },
            "round_number": round_number,
            "max_rounds": config.max_rounds,
            "scenario": config.scenario,
        }
        return self.provider.complete_agent_turn(payload)
