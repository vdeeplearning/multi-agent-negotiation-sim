from app.schemas import NegotiationState


class InMemoryNegotiationStore:
    def __init__(self) -> None:
        self._states: dict[str, NegotiationState] = {}

    def save(self, state: NegotiationState) -> NegotiationState:
        self._states[state.negotiation_id] = state
        return state

    def get(self, negotiation_id: str) -> NegotiationState | None:
        return self._states.get(negotiation_id)


store = InMemoryNegotiationStore()

