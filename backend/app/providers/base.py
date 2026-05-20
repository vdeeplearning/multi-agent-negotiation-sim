from abc import ABC, abstractmethod
from typing import Any

from app.schemas import AgentResponse, TokenUsage


class BaseLLMProvider(ABC):
    name: str
    provider: str
    model_name: str
    usage: TokenUsage

    @abstractmethod
    def complete_agent_turn(self, payload: dict[str, Any]) -> AgentResponse:
        """Return a structured agent response."""

    def add_usage(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens
        self.usage.total_tokens += input_tokens + output_tokens
        self.usage.approximate_cost_usd = estimate_cost(
            self.provider,
            self.model_name,
            self.usage.input_tokens,
            self.usage.output_tokens,
        )


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float | None:
    rates_per_million = {
        ("mock", "mock-negotiator-v1"): (0.0, 0.0),
        ("openai", "gpt-4o-mini"): (0.15, 0.6),
        ("openai", "gpt-4o"): (2.5, 10.0),
        ("anthropic", "claude-3-5-haiku-latest"): (0.8, 4.0),
        ("anthropic", "claude-3-5-sonnet-latest"): (3.0, 15.0),
    }
    key = (provider.lower(), model.lower())
    if key not in rates_per_million:
        return None
    input_rate, output_rate = rates_per_million[key]
    return round((input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate, 6)
