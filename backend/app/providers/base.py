from abc import ABC, abstractmethod
from typing import Any

from app.schemas import AgentResponse


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete_agent_turn(self, payload: dict[str, Any]) -> AgentResponse:
        """Return a structured agent response."""

