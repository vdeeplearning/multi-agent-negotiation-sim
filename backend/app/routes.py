from fastapi import APIRouter, HTTPException

from app.orchestrator import NegotiationOrchestrator
from app.schemas import NegotiationConfig, NegotiationState, StartNegotiationRequest
from app.store import store

router = APIRouter()


@router.get("/defaults", response_model=NegotiationConfig)
def defaults() -> NegotiationConfig:
    return NegotiationConfig()


@router.post("/negotiations/start", response_model=NegotiationState)
def start_negotiation(request: StartNegotiationRequest) -> NegotiationState:
    orchestrator = NegotiationOrchestrator(request.config)
    state = orchestrator.run()
    return store.save(state)


@router.get("/negotiations/{negotiation_id}", response_model=NegotiationState)
def get_negotiation(negotiation_id: str) -> NegotiationState:
    state = store.get(negotiation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return state

