from app.orchestrator import NegotiationOrchestrator
from app.schemas import AgentRole, NegotiationConfig, Offer, TranscriptEntry


def test_orchestrator_uses_compiled_langgraph() -> None:
    orchestrator = NegotiationOrchestrator(NegotiationConfig())

    assert type(orchestrator.graph).__name__ == "CompiledStateGraph"


def test_langgraph_orchestrator_runs_negotiation() -> None:
    state = NegotiationOrchestrator(NegotiationConfig()).run()

    assert state.current_round > 0
    assert state.status.value in {"accepted", "failed", "deadlocked", "walked_away", "max_rounds"}
    assert len(state.trace) > 0


def test_concession_explanation_for_buyer_price_retreat() -> None:
    orchestrator = NegotiationOrchestrator(NegotiationConfig())
    orchestrator.state.transcript = [
        TranscriptEntry(
            round_number=1,
            agent=AgentRole.BUYER,
            message="Initial buyer offer.",
            offer=Offer(price=85000, delivery_days=30, warranty="extended", contract_months=12),
            visible_reasoning_summary="Initial anchor.",
            accept=False,
            walk_away=False,
        ),
        TranscriptEntry(
            round_number=2,
            agent=AgentRole.SELLER,
            message="Seller counter.",
            offer=Offer(price=95000, delivery_days=21, warranty="standard", contract_months=18),
            visible_reasoning_summary="Seller improves price.",
            accept=False,
            walk_away=False,
        ),
        TranscriptEntry(
            round_number=3,
            agent=AgentRole.BUYER,
            message="Buyer concession.",
            offer=Offer(price=90000, delivery_days=30, warranty="extended", contract_months=12),
            visible_reasoning_summary="Buyer raises price.",
            accept=False,
            walk_away=False,
        ),
        TranscriptEntry(
            round_number=4,
            agent=AgentRole.SELLER,
            message="Seller worsens non-price terms.",
            offer=Offer(price=100000, delivery_days=28, warranty="standard", contract_months=24),
            visible_reasoning_summary="Seller asks for more.",
            accept=False,
            walk_away=False,
        ),
    ]

    explanation = orchestrator._concession_explanation(
        AgentRole.BUYER,
        Offer(price=85000, delivery_days=21, warranty="extended", contract_months=12),
    )

    assert explanation == "Concession explanation: buyer reduced price because seller worsened price, contract length, and delivery."
