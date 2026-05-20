from app.orchestrator import NegotiationOrchestrator
from app.schemas import NegotiationConfig


def test_orchestrator_uses_compiled_langgraph() -> None:
    orchestrator = NegotiationOrchestrator(NegotiationConfig())

    assert type(orchestrator.graph).__name__ == "CompiledStateGraph"


def test_langgraph_orchestrator_runs_negotiation() -> None:
    state = NegotiationOrchestrator(NegotiationConfig()).run()

    assert state.current_round > 0
    assert state.status.value in {"accepted", "failed", "deadlocked", "walked_away", "max_rounds"}
    assert len(state.trace) > 0
