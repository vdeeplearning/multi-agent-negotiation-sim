from app.evaluator import compute_utilities, detect_deadlock, evaluate_termination, evaluator_recommendation, is_offer_valid, validate_feasible_config
from app.schemas import AgentRole, NegotiationConfig, NegotiationStatus, Offer, SellerConfig, TranscriptEntry


def test_utility_prefers_buyer_friendly_offer() -> None:
    config = NegotiationConfig()
    strong_buyer_offer = Offer(price=88000, delivery_days=22, warranty="extended", contract_months=12)
    weak_buyer_offer = Offer(price=102000, delivery_days=44, warranty="basic", contract_months=30)

    assert compute_utilities(strong_buyer_offer, config).buyer > compute_utilities(weak_buyer_offer, config).buyer


def test_reservation_miss_is_still_valid_offer() -> None:
    config = NegotiationConfig()
    offer = Offer(price=81000, delivery_days=50, warranty="standard", contract_months=12)

    assert is_offer_valid(offer, config) is True


def test_infeasible_price_config_is_explained() -> None:
    config = NegotiationConfig(seller=SellerConfig(minimum_acceptable_price=104000))

    reason = validate_feasible_config(config)

    assert reason is not None
    assert "No feasible price range" in reason


def test_acceptance_requires_valid_offer_and_utility() -> None:
    config = NegotiationConfig()
    offer = Offer(price=94000, delivery_days=28, warranty="standard", contract_months=18)
    entry = TranscriptEntry(
        round_number=5,
        agent=AgentRole.SELLER,
        message="Accepted.",
        offer=offer,
        visible_reasoning_summary="Commercial terms are workable.",
        accept=True,
        walk_away=False,
    )

    status, _ = evaluate_termination([entry], compute_utilities(offer, config), config)
    assert status == NegotiationStatus.ACCEPTED


def test_evaluator_recommends_acceptance_for_mutual_viability() -> None:
    config = NegotiationConfig()
    offer = Offer(price=95000, delivery_days=25, warranty="standard", contract_months=24)
    utilities = compute_utilities(offer, config)

    guidance = evaluator_recommendation(utilities)

    assert guidance is not None
    assert "Strongly consider accepting" in guidance


def test_deadlock_detects_low_movement_recent_offers() -> None:
    offers = [
        Offer(price=95000, delivery_days=30, warranty="standard", contract_months=18),
        Offer(price=96000, delivery_days=31, warranty="standard", contract_months=18),
        Offer(price=95200, delivery_days=30, warranty="standard", contract_months=18),
        Offer(price=96100, delivery_days=31, warranty="standard", contract_months=18),
    ]
    transcript = [
        TranscriptEntry(
            round_number=i + 1,
            agent=AgentRole.BUYER if i % 2 == 0 else AgentRole.SELLER,
            message="Counter.",
            offer=offer,
            visible_reasoning_summary="Limited movement.",
            accept=False,
            walk_away=False,
        )
        for i, offer in enumerate(offers)
    ]

    assert detect_deadlock(transcript) is True
