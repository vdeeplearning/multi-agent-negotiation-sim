from app.providers.base import LLMProvider
from app.providers.mock import MockProvider


def get_provider(name: str) -> LLMProvider:
    normalized = name.lower().strip()
    if normalized in {"mock", "openai", "anthropic"}:
        return MockProvider(provider_name=normalized)
    raise ValueError(f"Unsupported provider: {name}")

