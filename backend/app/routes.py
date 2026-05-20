from fastapi import APIRouter, Header, HTTPException

from app.orchestrator import NegotiationOrchestrator
from app.schemas import NegotiationConfig, NegotiationState, ProviderRuntimeConfig, StartNegotiationRequest
from app.store import store

router = APIRouter()


@router.get("/defaults", response_model=NegotiationConfig)
def defaults() -> NegotiationConfig:
    return NegotiationConfig()


def _runtime_from_headers(
    config: NegotiationConfig,
    provider: str | None,
    model: str | None,
    api_key: str | None,
) -> ProviderRuntimeConfig:
    requested_provider = (provider or config.provider or "mock").lower().strip()
    model_name = model or config.model_name
    if requested_provider == "openai" and not model_name:
        model_name = "gpt-4o-mini"
    if requested_provider == "anthropic" and not model_name:
        model_name = "claude-3-5-haiku-latest"
    if requested_provider == "mock":
        model_name = model_name or "mock-negotiator-v1"
        return ProviderRuntimeConfig(
            requested_provider=requested_provider,
            active_provider="mock",
            model_name=model_name,
        )
    if requested_provider not in {"openai", "anthropic"}:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {requested_provider}")
    if not api_key:
        return ProviderRuntimeConfig(
            requested_provider=requested_provider,
            active_provider="mock",
            model_name="mock-negotiator-v1",
            fallback_reason=f"No API key supplied for {requested_provider}; fell back to Mock Mode.",
        )
    return ProviderRuntimeConfig(
        requested_provider=requested_provider,
        active_provider=requested_provider,
        model_name=model_name,
        api_key=api_key,
    )


@router.post("/negotiations/start", response_model=NegotiationState)
def start_negotiation(
    request: StartNegotiationRequest,
    x_llm_provider: str | None = Header(default=None),
    x_llm_model: str | None = Header(default=None),
    x_llm_api_key: str | None = Header(default=None),
) -> NegotiationState:
    runtime = _runtime_from_headers(request.config, x_llm_provider, x_llm_model, x_llm_api_key)
    clean_config = request.config.model_copy(update={"provider": runtime.active_provider, "model_name": runtime.model_name})
    orchestrator = NegotiationOrchestrator(clean_config, runtime)
    state = orchestrator.run()
    return store.save(state)


@router.get("/negotiations/{negotiation_id}", response_model=NegotiationState)
def get_negotiation(negotiation_id: str) -> NegotiationState:
    state = store.get(negotiation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return state
