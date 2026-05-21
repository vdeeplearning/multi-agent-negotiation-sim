from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import NegotiationAgent
from app.evaluator import compute_utilities, evaluate_termination, evaluator_recommendation, is_offer_valid, validate_feasible_config
from app.providers import get_provider
from app.schemas import (
    AgentRole,
    NegotiationConfig,
    Offer,
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
    def __init__(
        self,
        config: NegotiationConfig,
        runtime: ProviderRuntimeConfig | None = None,
        failure_mode: str | None = None,
    ) -> None:
        self.config = config
        self.failure_mode = failure_mode
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
        if self.failure_mode:
            self._trace(
                "failure_mode_injected",
                f"Controlled mock failure mode requested: {self.failure_mode}.",
            )
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
        self._trace("provider_selected", self.provider.name, actor.role)

        try:
            response = actor.act(
                config=self.config,
                history=self.state.transcript,
                latest_offer=self.state.latest_offer,
                round_number=round_number,
                evaluator_guidance=guidance,
                failure_mode=self.failure_mode,
            )
            self._trace("raw_response_received", "Provider returned a candidate agent response.", actor.role)
            self._trace("structured_response_parsed", "Structured response parsed into AgentResponse.", actor.role)
        except Exception as exc:
            self.state.status = NegotiationStatus.FAILED
            self.state.provider_info.token_usage = self.provider.usage
            self.state.outcome_summary = "Provider response could not be parsed or validated."
            self._trace("schema_validation_failed", f"Provider response rejected: {exc}", actor.role)
            self._trace("termination_condition_checked", self.state.status.value, actor.role)
            return {
                "negotiation": self.state,
                "evaluator_guidance": None,
            }

        entry = TranscriptEntry(
            round_number=round_number,
            agent=actor.role,
            message=response.message,
            offer=response.offer,
            visible_reasoning_summary=response.visible_reasoning_summary,
            concession_explanation=self._concession_explanation(actor.role, response.offer),
            accept=response.accept,
            walk_away=response.walk_away,
        )
        self.state.transcript.append(entry)
        self.state.latest_offer = response.offer
        self.state.current_round = round_number

        if not is_offer_valid(response.offer, self.config):
            self.state.status = NegotiationStatus.FAILED
            self.state.provider_info.token_usage = self.provider.usage
            self.state.outcome_summary = "Latest offer was malformed or outside the public offer schema."
            self._trace("schema_validation_failed", "Offer failed deterministic public offer validation.", actor.role)
            self._trace("termination_condition_checked", self.state.status.value, actor.role)
            return {
                "negotiation": self.state,
                "evaluator_guidance": None,
            }
        self._trace("schema_validation_passed", "Agent response and offer passed deterministic validation.", actor.role)

        utilities = compute_utilities(response.offer, self.config)
        self.state.utility_history.append(utilities)
        self._trace("offer_evaluated", "Offer evaluated by deterministic scoring rules.", actor.role)
        self._trace(
            "utility_scores_updated",
            f"Buyer utility {utilities.buyer}; seller utility {utilities.seller}.",
            actor.role,
        )
        next_guidance = evaluator_recommendation(utilities)
        if next_guidance:
            self._trace("evaluator_recommendation", next_guidance, actor.role)

        status, summary = evaluate_termination(self.state.transcript, utilities, self.config)
        self.state.status = status
        self.state.provider_info.token_usage = self.provider.usage
        if status == NegotiationStatus.DEADLOCKED:
            self._trace("deadlock_detected", "Recent offers show repeated low-movement terms.", actor.role)
        if status == NegotiationStatus.WALKED_AWAY:
            self._trace("walk_away_detected", f"{actor.role.value.title()} set walk_away=true.", actor.role)
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

    def _concession_explanation(self, actor: AgentRole, offer: Offer) -> str | None:
        previous_same = [entry for entry in self.state.transcript if entry.agent == actor]
        if not previous_same:
            return None

        prior_offer = previous_same[-1].offer
        if actor == AgentRole.BUYER and offer.price < prior_offer.price:
            reasons = self._worsened_terms_for_buyer()
            return self._format_concession_explanation(
                actor="buyer",
                action="reduced price",
                counterparty="seller",
                reasons=reasons,
            )
        if actor == AgentRole.SELLER and offer.price > prior_offer.price:
            reasons = self._worsened_terms_for_seller()
            return self._format_concession_explanation(
                actor="seller",
                action="increased price",
                counterparty="buyer",
                reasons=reasons,
            )
        return None

    def _worsened_terms_for_buyer(self) -> list[str]:
        seller_entries = [entry for entry in self.state.transcript if entry.agent == AgentRole.SELLER]
        if len(seller_entries) < 2:
            return []
        previous = seller_entries[-2].offer
        latest = seller_entries[-1].offer
        reasons = []
        if latest.price > previous.price:
            reasons.append("price")
        if self._warranty_distance(latest.warranty, self.config.buyer.preferred_warranty) > self._warranty_distance(previous.warranty, self.config.buyer.preferred_warranty):
            reasons.append("warranty")
        if abs(latest.contract_months - self.config.buyer.preferred_contract_months) > abs(previous.contract_months - self.config.buyer.preferred_contract_months):
            reasons.append("contract length")
        if abs(latest.delivery_days - self.config.buyer.preferred_delivery_days) > abs(previous.delivery_days - self.config.buyer.preferred_delivery_days):
            reasons.append("delivery")
        return reasons

    def _worsened_terms_for_seller(self) -> list[str]:
        buyer_entries = [entry for entry in self.state.transcript if entry.agent == AgentRole.BUYER]
        if len(buyer_entries) < 2:
            return []
        previous = buyer_entries[-2].offer
        latest = buyer_entries[-1].offer
        reasons = []
        if latest.price < previous.price:
            reasons.append("price")
        if self._warranty_distance(latest.warranty, self.config.seller.preferred_warranty) > self._warranty_distance(previous.warranty, self.config.seller.preferred_warranty):
            reasons.append("warranty")
        if abs(latest.contract_months - self.config.seller.preferred_contract_months) > abs(previous.contract_months - self.config.seller.preferred_contract_months):
            reasons.append("contract length")
        if abs(latest.delivery_days - self.config.seller.preferred_delivery_days) > abs(previous.delivery_days - self.config.seller.preferred_delivery_days):
            reasons.append("delivery")
        return reasons

    def _format_concession_explanation(self, actor: str, action: str, counterparty: str, reasons: list[str]) -> str:
        if reasons:
            return f"Concession explanation: {actor} {action} because {counterparty} worsened {self._join_reasons(reasons)}."
        return f"Concession explanation: {actor} {action} because {counterparty}'s latest terms did not improve enough to support the prior price concession."

    def _join_reasons(self, reasons: list[str]) -> str:
        unique_reasons = list(dict.fromkeys(reasons))
        if len(unique_reasons) == 1:
            return unique_reasons[0]
        if len(unique_reasons) == 2:
            return f"{unique_reasons[0]} and {unique_reasons[1]}"
        return f"{', '.join(unique_reasons[:-1])}, and {unique_reasons[-1]}"

    def _warranty_distance(self, actual: str, preferred: str) -> int:
        order = {"basic": 0, "standard": 1, "extended": 2}
        return abs(order[actual] - order[preferred])

    def _trace(self, event_type: str, detail: str, actor: AgentRole | None = None) -> None:
        self.state.trace.append(
            TraceEvent(
                index=len(self.state.trace) + 1,
                event_type=event_type,
                detail=detail,
                actor=actor,
            )
        )
