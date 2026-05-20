from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import NegotiationAgent
from app.evaluator import compute_utilities, evaluate_termination, evaluator_recommendation, validate_feasible_config
from app.providers import get_provider
from app.schemas import (
    AgentRole,
    NegotiationConfig,
    ProviderRunInfo,
    ProviderRuntimeConfig,
    NegotiationState,
    NegotiationStatus,
    TraceEvent,
    TranscriptEntry,
)


class NegotiationGraphState(TypedDict):
    negotiation: NegotiationState
    evaluator_guidance: str | None


class NegotiationOrchestrator:
    def __init__(self, config: NegotiationConfig, runtime: ProviderRuntimeConfig | None = None) -> None:
        self.config = config
        self.runtime = runtime or ProviderRuntimeConfig(
            requested_provider=config.provider,
            active_provider=config.provider,
            model_name=config.model_name,
        )
        self.provider = get_provider(self.runtime)
        self.buyer = NegotiationAgent(AgentRole.BUYER, self.provider)
        self.seller = NegotiationAgent(AgentRole.SELLER, self.provider)
        self.state = NegotiationState(
            config=config,
            status=NegotiationStatus.RUNNING,
            provider_info=ProviderRunInfo(
                requested_provider=self.runtime.requested_provider,
                active_provider=self.runtime.active_provider,
                model_name=self.runtime.model_name,
                fallback_reason=self.runtime.fallback_reason,
            ),
        )
        if self.runtime.fallback_reason:
            self._trace("provider_fallback", self.runtime.fallback_reason)
        self.graph = self._build_graph()

    def run(self) -> NegotiationState:
        result = self.graph.invoke(
            {
                "negotiation": self.state,
                "evaluator_guidance": None,
            }
        )
        self.state = result["negotiation"]
        return self.state

    def _build_graph(self):
        workflow = StateGraph(NegotiationGraphState)
        workflow.add_node("preflight", self._preflight_node)
        workflow.add_node("agent_turn", self._agent_turn_node)
        workflow.add_edge(START, "preflight")
        workflow.add_conditional_edges(
            "preflight",
            self._route_next,
            {"continue": "agent_turn", "end": END},
        )
        workflow.add_conditional_edges(
            "agent_turn",
            self._route_next,
            {"continue": "agent_turn", "end": END},
        )
        return workflow.compile()

    def _preflight_node(self, graph_state: NegotiationGraphState) -> NegotiationGraphState:
        infeasible_reason = validate_feasible_config(self.config)
        if infeasible_reason:
            self._trace("configuration_checked", infeasible_reason)
        return {
            "negotiation": self.state,
            "evaluator_guidance": graph_state.get("evaluator_guidance"),
        }

    def _agent_turn_node(self, graph_state: NegotiationGraphState) -> NegotiationGraphState:
        guidance = graph_state.get("evaluator_guidance")
        actor = self.buyer if self.state.current_round % 2 == 0 else self.seller
        round_number = self.state.current_round + 1
        self._trace("agent_called", f"{actor.role.value.title()} agent invoked.", actor.role)
        self._trace("tool_model_used", self.provider.name, actor.role)

        response = actor.act(
            config=self.config,
            history=self.state.transcript,
            latest_offer=self.state.latest_offer,
            round_number=round_number,
            evaluator_guidance=guidance,
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
        next_guidance = evaluator_recommendation(utilities)
        if next_guidance:
            self._trace("evaluator_recommendation", next_guidance, actor.role)

        status, summary = evaluate_termination(self.state.transcript, utilities, self.config)
        self.state.status = status
        self.state.provider_info.token_usage = self.provider.usage
        self._trace("termination_condition_checked", status.value, actor.role)
        if summary:
            self.state.outcome_summary = summary

        return {
            "negotiation": self.state,
            "evaluator_guidance": next_guidance,
        }

    def _route_next(self, graph_state: NegotiationGraphState) -> Literal["continue", "end"]:
        negotiation = graph_state["negotiation"]
        return "continue" if negotiation.status == NegotiationStatus.RUNNING else "end"

    def _trace(self, event_type: str, detail: str, actor: AgentRole | None = None) -> None:
        self.state.trace.append(
            TraceEvent(
                index=len(self.state.trace) + 1,
                event_type=event_type,
                detail=detail,
                actor=actor,
            )
        )
