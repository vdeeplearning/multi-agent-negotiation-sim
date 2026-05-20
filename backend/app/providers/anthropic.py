import json
import urllib.error
import urllib.request
from typing import Any

from app.providers.base import BaseLLMProvider
from app.providers.prompting import build_agent_prompt, extract_json_text
from app.schemas import AgentResponse, TokenUsage


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str = "claude-3-5-haiku-latest") -> None:
        self.provider = "anthropic"
        self.model_name = model_name or "claude-3-5-haiku-latest"
        self.name = f"Anthropic ({self.model_name})"
        self.api_key = api_key
        self.usage = TokenUsage()

    def complete_agent_turn(self, payload: dict[str, Any]) -> AgentResponse:
        body = {
            "model": self.model_name,
            "max_tokens": 700,
            "system": "Return only valid JSON matching the requested schema. Do not expose private goals.",
            "messages": [{"role": "user", "content": build_agent_prompt(payload)}],
        }
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic request failed: {exc.code} {detail}") from exc

        usage = data.get("usage", {})
        self.add_usage(
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
        )
        output_text = "".join(
            item.get("text", "")
            for item in data.get("content", [])
            if item.get("type") == "text"
        )
        return AgentResponse.model_validate_json(extract_json_text(output_text))

