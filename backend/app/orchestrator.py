from app.agents import NegotiationAgent
from app.evaluator import compute_utilities, evaluate_termination
from app.providers import get_provider
from app.schemas import (
    AgentRole,
    NegotiationConfig,
    NegotiationState,
    NegotiationStatus,
    TraceEvent,
    TranscriptEntry,
)


class NegotiationOrchestrator:
    def __init__(self, config: NegotiationConfig) -> None:
        self.config = config
        self.provider = get_provider(config.provider)
        self.buyer = NegotiationAgent(AgentRole.BUYER, self.provider)
        self.seller = NegotiationAgent(AgentRole.SELLER, self.provider)
        self.state = NegotiationState(config=config, status=NegotiationStatus.RUNNING)

    def run(self) -> NegotiationState:
        while self.state.status == NegotiationStatus.RUNNING:
            actor = self.buyer if self.state.current_round % 2 == 0 else self.seller
            round_number = self.state.current_round + 1
            self._trace("agent_called", f"{actor.role.value.title()} agent invoked.", actor.role)
            self._trace("tool_model_used", self.provider.name, actor.role)

            response = actor.act(
                config=self.config,
                history=self.state.transcript,
                latest_offer=self.state.latest_offer,
                round_number=round_number,
            )
            self._trace("offer_parsed", "Structured JSON response validated with Pydantic.", actor.role)

            entry = TranscriptEntry(
                round_number=round_number,
                agent=actor.role,
                message=response.message,
                offer=response.offer,
                visible_reasoning_summary=response.visible_reasoning_summary,
                accept=response.accept,
                walk_away=response.walk_away,
            )
            self.state.transcript.append(entry)
            self.state.latest_offer = response.offer
            self.state.current_round = round_number

            utilities = compute_utilities(response.offer, self.config)
            self.state.utility_history.append(utilities)
            self._trace(
                "evaluator_updated_state",
                f"Buyer utility {utilities.buyer}; seller utility {utilities.seller}.",
                actor.role,
            )

            status, summary = evaluate_termination(self.state.transcript, utilities, self.config)
            self.state.status = status
            self._trace("termination_condition_checked", status.value, actor.role)
            if summary:
                self.state.outcome_summary = summary

        return self.state

    def _trace(self, event_type: str, detail: str, actor: AgentRole | None = None) -> None:
        self.state.trace.append(
            TraceEvent(
                index=len(self.state.trace) + 1,
                event_type=event_type,
                detail=detail,
                actor=actor,
            )
        )

