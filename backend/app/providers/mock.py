from typing import Any

from app.providers.base import BaseLLMProvider
from app.schemas import AgentResponse, AgentRole, BuyerConfig, Offer, SellerConfig, TokenUsage


class MockProvider(BaseLLMProvider):
    """Deterministic provider that mimics structured LLM responses."""

    def __init__(self, model_name: str = "mock-negotiator-v1", provider_name: str = "mock") -> None:
        self.provider = "mock"
        self.model_name = model_name or "mock-negotiator-v1"
        self.name = f"{provider_name}-mock-adapter ({self.model_name})"
        self.usage = TokenUsage()

    def complete_agent_turn(self, payload: dict[str, Any]) -> AgentResponse:
        role: AgentRole = payload["role"]
        round_number: int = payload["round_number"]
        max_rounds: int = payload["max_rounds"]
        latest_offer: Offer | None = payload.get("latest_offer")
        failure_mode: str | None = payload.get("failure_mode")
        self.add_usage(input_tokens=420 + len(payload.get("public_history", [])) * 110, output_tokens=145)
        if failure_mode == "malformed_json" and round_number == 1:
            raise ValueError("mock injected malformed_json response before schema parsing")
        if failure_mode == "invalid_offer" and round_number == 1:
            return AgentResponse.model_construct(
                message="Injected invalid offer for evaluator demonstration.",
                offer=Offer.model_construct(price=-1, delivery_days=0, warranty="standard", contract_months=0),
                visible_reasoning_summary="This is a controlled invalid-offer demo for observability testing.",
                accept=False,
                walk_away=False,
            )
        if failure_mode == "premature_walkaway" and round_number == 1:
            return AgentResponse(
                message="I am walking away before there is enough negotiation history.",
                offer=Offer(price=90000, delivery_days=30, warranty="standard", contract_months=12),
                visible_reasoning_summary="This controlled demo shows how premature walk-away is detected and terminated.",
                accept=False,
                walk_away=True,
            )
        if failure_mode == "deadlock_bias":
            return self._deadlock_turn(role, round_number)
        demo_accept_round = min(max_rounds, 8)
        if payload.get("evaluator_guidance") and latest_offer and round_number >= demo_accept_round:
            return AgentResponse(
                message="I can accept this offer because the evaluator indicates it is mutually viable.",
                offer=latest_offer,
                visible_reasoning_summary="The latest package appears workable for both sides, so accepting avoids unnecessary negotiation drift.",
                accept=True,
                walk_away=False,
            )
        if role == AgentRole.BUYER:
            return self._buyer_turn(payload["private_config"], latest_offer, round_number, max_rounds)
        return self._seller_turn(payload["private_config"], latest_offer, round_number, max_rounds)

    def _deadlock_turn(self, role: AgentRole, round_number: int) -> AgentResponse:
        return AgentResponse(
            message="I am holding near the same terms to demonstrate a low-movement deadlock.",
            offer=Offer(price=101000, delivery_days=25, warranty="standard", contract_months=24),
            visible_reasoning_summary=(
                f"The {role.value} is deliberately showing minimal movement so the deterministic deadlock detector can be observed."
            ),
            accept=False,
            walk_away=False,
        )

    def _buyer_turn(
        self,
        config: BuyerConfig,
        latest_offer: Offer | None,
        round_number: int,
        max_rounds: int,
    ) -> AgentResponse:
        urgency = round_number / max_rounds
        if latest_offer and latest_offer.price <= config.maximum_acceptable_price and latest_offer.delivery_days <= config.max_delivery_days:
            acceptable_warranty = latest_offer.warranty == config.preferred_warranty or config.risk_tolerance > 0.7
            accept = acceptable_warranty and round_number >= min(max_rounds, 8)
            if accept:
                return AgentResponse(
                    message="I can accept this package because it balances cost control with operational coverage.",
                    offer=latest_offer,
                    visible_reasoning_summary="The latest proposal is inside the buyer's acceptable commercial range and reduces deployment risk.",
                    accept=True,
                    walk_away=False,
                )

        concession_floor = 0.3
        anchor = config.target_price + (config.maximum_acceptable_price - config.target_price) * max(
            concession_floor,
            min(0.8, urgency * 0.9),
        )
        price = latest_offer.price - 4500 if latest_offer else anchor
        price = min(config.maximum_acceptable_price, max(config.target_price, price))
        delivery = min(config.max_delivery_days, config.preferred_delivery_days + round(urgency * 12))
        contract = config.preferred_contract_months if urgency < 0.7 else config.preferred_contract_months + 6
        warranty = config.preferred_warranty
        walk = latest_offer is not None and round_number >= max_rounds and latest_offer.price > config.maximum_acceptable_price
        return AgentResponse(
            message=f"I can move to ${price:,.0f} with {delivery} day delivery if warranty remains {warranty}.",
            offer=Offer(price=round(price), delivery_days=delivery, warranty=warranty, contract_months=contract),
            visible_reasoning_summary="The buyer is making a controlled concession while preserving deployment assurance and budget discipline.",
            accept=False,
            walk_away=walk,
        )

    def _seller_turn(
        self,
        config: SellerConfig,
        latest_offer: Offer | None,
        round_number: int,
        max_rounds: int,
    ) -> AgentResponse:
        urgency = round_number / max_rounds
        if latest_offer and latest_offer.price >= config.minimum_acceptable_price and latest_offer.delivery_days >= config.minimum_delivery_days:
            warranty_load_ok = latest_offer.warranty == config.preferred_warranty or latest_offer.contract_months >= 18 or latest_offer.price > config.minimum_acceptable_price + 9000
            accept = warranty_load_ok and round_number >= min(max_rounds, 8)
            if accept:
                return AgentResponse(
                    message="I can accept this structure because the commitment and service scope are commercially workable.",
                    offer=latest_offer,
                    visible_reasoning_summary="The seller sees enough margin protection and operational flexibility in the current package.",
                    accept=True,
                    walk_away=False,
                )

        anchor = config.target_price - (config.target_price - config.minimum_acceptable_price) * min(0.85, urgency * 0.8)
        price = latest_offer.price + 5000 if latest_offer else anchor
        price = max(config.minimum_acceptable_price, min(config.target_price, price))
        delivery = max(config.minimum_delivery_days, config.preferred_delivery_days - round(urgency * 10))
        contract = config.preferred_contract_months if urgency < 0.6 else max(18, config.preferred_contract_months - 6)
        warranty = config.preferred_warranty if urgency < 0.75 else latest_offer.warranty if latest_offer else config.preferred_warranty
        walk = latest_offer is not None and round_number >= max_rounds and latest_offer.price < config.minimum_acceptable_price
        return AgentResponse(
            message=f"I can offer ${price:,.0f}, {delivery} day delivery, {warranty} warranty, and {contract} months.",
            offer=Offer(price=round(price), delivery_days=delivery, warranty=warranty, contract_months=contract),
            visible_reasoning_summary="The seller is narrowing price and service terms while protecting delivery feasibility and contract value.",
            accept=False,
            walk_away=walk,
        )
