from app.routes import start_negotiation
from app.schemas import NegotiationConfig, StartNegotiationRequest


def test_failure_mode_forces_mock_runtime_when_provider_header_is_openai() -> None:
    request = StartNegotiationRequest(
        config=NegotiationConfig(provider="openai", model_name="gpt-4o-mini"),
        failure_mode="malformed_json",
    )

    state = start_negotiation(
        request=request,
        x_llm_provider="openai",
        x_llm_model="gpt-4o-mini",
        x_llm_api_key="not-used-for-failure-demo",
    )

    assert state.provider_info.requested_provider == "openai"
    assert state.provider_info.active_provider == "mock"
    assert state.provider_info.model_name == "mock-negotiator-v1"
    assert state.status.value == "failed"
    assert any(event.event_type == "schema_validation_failed" for event in state.trace)
