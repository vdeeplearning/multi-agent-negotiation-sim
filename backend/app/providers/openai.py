import json
import urllib.error
import urllib.request
from typing import Any

from app.providers.base import BaseLLMProvider
from app.providers.prompting import AGENT_RESPONSE_SCHEMA, build_agent_prompt, extract_json_text
from app.schemas import AgentResponse, TokenUsage


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini") -> None:
        self.provider = "openai"
        self.model_name = model_name or "gpt-4o-mini"
        self.name = f"OpenAI ({self.model_name})"
        self.api_key = api_key
        self.usage = TokenUsage()

    def complete_agent_turn(self, payload: dict[str, Any]) -> AgentResponse:
        prompt = build_agent_prompt(payload)
        body = {
            "model": self.model_name,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agent_response",
                    "strict": True,
                    "schema": AGENT_RESPONSE_SCHEMA,
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed: {exc.code} {detail}") from exc

        usage = data.get("usage", {})
        self.add_usage(
            input_tokens=int(usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or usage.get("completion_tokens", 0) or 0),
        )
        output_text = data.get("output_text")
        if not output_text:
            output_text = "".join(
                content.get("text", "")
                for item in data.get("output", [])
                for content in item.get("content", [])
                if content.get("type") in {"output_text", "text"}
            )
        return AgentResponse.model_validate_json(extract_json_text(output_text))

