from app.schemas import (
    AgentRole,
    BuyerConfig,
    NegotiationConfig,
    NegotiationStatus,
    Offer,
    SellerConfig,
    TranscriptEntry,
    UtilityScore,
)

WARRANTY_BUYER_VALUE = {"basic": 10, "standard": 60, "extended": 100}
WARRANTY_SELLER_COST = {"basic": 100, "standard": 65, "extended": 25}


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def buyer_utility(offer: Offer, config: BuyerConfig) -> float:
    price_band = config.maximum_acceptable_price - config.target_price
    price_score = 100 if price_band <= 0 else 100 - ((offer.price - config.target_price) / price_band) * 65
    delivery_score = 100 - max(0, offer.delivery_days - config.preferred_delivery_days) * 4
    contract_score = 100 - abs(offer.contract_months - config.preferred_contract_months) * 3
    warranty_score = WARRANTY_BUYER_VALUE[offer.warranty]
    weighted = price_score * 0.42 + delivery_score * 0.22 + warranty_score * 0.2 + contract_score * 0.16
    return round(_clamp(weighted), 1)


def seller_utility(offer: Offer, config: SellerConfig) -> float:
    price_band = config.target_price - config.minimum_acceptable_price
    price_score = 100 if price_band <= 0 else 100 - ((config.target_price - offer.price) / price_band) * 65
    delivery_score = 100 - max(0, config.preferred_delivery_days - offer.delivery_days) * 4
    contract_score = 100 - abs(offer.contract_months - config.preferred_contract_months) * 2.4
    warranty_score = WARRANTY_SELLER_COST[offer.warranty]
    weighted = price_score * 0.46 + delivery_score * 0.19 + warranty_score * 0.2 + contract_score * 0.15
    return round(_clamp(weighted), 1)


def compute_utilities(offer: Offer, config: NegotiationConfig) -> UtilityScore:
    return UtilityScore(
        buyer=buyer_utility(offer, config.buyer),
        seller=seller_utility(offer, config.seller),
    )


def is_offer_valid(offer: Offer, config: NegotiationConfig) -> bool:
    return (
        offer.price <= config.buyer.maximum_acceptable_price
        and offer.price >= config.seller.minimum_acceptable_price
        and offer.delivery_days <= config.buyer.max_delivery_days
        and offer.delivery_days >= config.seller.minimum_delivery_days
    )


def validate_feasible_config(config: NegotiationConfig) -> str | None:
    if config.seller.minimum_acceptable_price > config.buyer.maximum_acceptable_price:
        return (
            "No feasible price range: seller minimum acceptable price "
            f"(${config.seller.minimum_acceptable_price:,.0f}) exceeds buyer maximum acceptable price "
            f"(${config.buyer.maximum_acceptable_price:,.0f})."
        )
    if config.seller.minimum_delivery_days > config.buyer.max_delivery_days:
        return (
            "No feasible delivery range: seller minimum delivery days "
            f"({config.seller.minimum_delivery_days}) exceeds buyer maximum delivery days "
            f"({config.buyer.max_delivery_days})."
        )
    return None


def detect_deadlock(transcript: list[TranscriptEntry]) -> bool:
    if len(transcript) < 4:
        return False
    recent = transcript[-4:]
    prices = [entry.offer.price for entry in recent]
    deliveries = [entry.offer.delivery_days for entry in recent]
    contracts = [entry.offer.contract_months for entry in recent]
    price_stalled = max(prices) - min(prices) <= 1500
    delivery_stalled = max(deliveries) - min(deliveries) <= 2
    contract_stalled = max(contracts) - min(contracts) <= 1
    no_acceptance = not any(entry.accept for entry in recent)
    return price_stalled and delivery_stalled and contract_stalled and no_acceptance


def evaluate_termination(
    transcript: list[TranscriptEntry],
    utilities: UtilityScore,
    config: NegotiationConfig,
) -> tuple[NegotiationStatus, str | None]:
    latest = transcript[-1]
    if latest.walk_away:
        return NegotiationStatus.WALKED_AWAY, f"{latest.agent.value.title()} walked away from the negotiation."
    if not is_offer_valid(latest.offer, config):
        return NegotiationStatus.FAILED, "Latest offer violated one or more hard constraints."
    if latest.accept and utilities.buyer >= 58 and utilities.seller >= 58:
        return NegotiationStatus.ACCEPTED, "Both parties reached an acceptable utility range and accepted the contract."
    if detect_deadlock(transcript):
        return NegotiationStatus.DEADLOCKED, "Negotiation deadlocked after repeated low-movement offers."
    if latest.round_number >= config.max_rounds:
        return NegotiationStatus.MAX_ROUNDS, "Maximum rounds reached without mutual acceptance."
    return NegotiationStatus.RUNNING, None
