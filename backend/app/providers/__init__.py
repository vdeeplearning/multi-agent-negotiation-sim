from app.providers.anthropic import AnthropicProvider
from app.providers.base import BaseLLMProvider
from app.providers.mock import MockProvider
from app.providers.openai import OpenAIProvider
from app.schemas import ProviderRuntimeConfig


def get_provider(runtime: ProviderRuntimeConfig) -> BaseLLMProvider:
    normalized = runtime.active_provider.lower().strip()
    if normalized == "mock":
        return MockProvider(model_name=runtime.model_name, provider_name=runtime.requested_provider)
    if normalized == "openai":
        return OpenAIProvider(api_key=runtime.api_key or "", model_name=runtime.model_name)
    if normalized == "anthropic":
        return AnthropicProvider(api_key=runtime.api_key or "", model_name=runtime.model_name)
    raise ValueError(f"Unsupported provider: {runtime.active_provider}")
