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
        evaluator_guidance: str | None = None,
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
                "accept_mutually_viable_guidance": (
                    "If evaluator_guidance says the latest offer is mutually viable, and the latest offer does not "
                    "violate your private constraints, prefer returning accept=true over making another counteroffer."
                ),
            },
            "round_number": round_number,
            "max_rounds": config.max_rounds,
            "scenario": config.scenario,
            "evaluator_guidance": evaluator_guidance,
        }
        return self.provider.complete_agent_turn(payload)
