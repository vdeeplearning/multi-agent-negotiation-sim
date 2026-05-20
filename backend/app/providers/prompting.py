import json
from typing import Any

from app.schemas import AgentRole, Offer


AGENT_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "message": {"type": "string"},
        "offer": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "price": {"type": "number"},
                "delivery_days": {"type": "integer"},
                "warranty": {"type": "string", "enum": ["basic", "standard", "extended"]},
                "contract_months": {"type": "integer"},
            },
            "required": ["price", "delivery_days", "warranty", "contract_months"],
        },
        "visible_reasoning_summary": {"type": "string"},
        "accept": {"type": "boolean"},
        "walk_away": {"type": "boolean"},
    },
    "required": ["message", "offer", "visible_reasoning_summary", "accept", "walk_away"],
}


def build_agent_prompt(payload: dict[str, Any]) -> str:
    role: AgentRole = payload["role"]
    latest_offer: Offer | None = payload.get("latest_offer")
    private_config = payload["private_config"]
    history = [
        {
            "round_number": entry.round_number,
            "agent": entry.agent.value,
            "message": entry.message,
            "offer": entry.offer.model_dump(),
            "accept": entry.accept,
            "walk_away": entry.walk_away,
        }
        for entry in payload.get("public_history", [])
    ]
    task = {
        "role": role.value,
        "scenario": payload["scenario"],
        "round_number": payload["round_number"],
        "max_rounds": payload["max_rounds"],
        "private_config_for_this_agent_only": private_config.model_dump(),
        "public_history": history,
        "latest_offer": latest_offer.model_dump() if latest_offer else None,
        "constraints": payload["system_constraints"],
        "response_schema": AGENT_RESPONSE_SCHEMA,
    }
    return (
        "You are one agent in a contract negotiation. Return only valid JSON matching "
        "the provided schema. Do not reveal private config values directly, hidden priorities, "
        "reservation prices, or hidden constraints. visible_reasoning_summary must be a concise "
        "public rationale, not hidden chain-of-thought.\n\n"
        f"{json.dumps(task, indent=2)}"
    )


def extract_json_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end >= start:
        return stripped[start : end + 1]
    return stripped

