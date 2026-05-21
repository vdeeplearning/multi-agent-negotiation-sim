from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


WarrantyLevel = Literal["basic", "standard", "extended"]


class AgentRole(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"


class NegotiationStatus(str, Enum):
    CONFIGURED = "configured"
    RUNNING = "running"
    ACCEPTED = "accepted"
    FAILED = "failed"
    DEADLOCKED = "deadlocked"
    WALKED_AWAY = "walked_away"
    MAX_ROUNDS = "max_rounds"


class Offer(BaseModel):
    price: float = Field(gt=0)
    delivery_days: int = Field(gt=0)
    warranty: WarrantyLevel
    contract_months: int = Field(gt=0)


class BuyerConfig(BaseModel):
    target_price: float = 82000
    maximum_acceptable_price: float = 103000
    preferred_delivery_days: int = 21
    max_delivery_days: int = 45
    preferred_contract_months: int = 12
    preferred_warranty: WarrantyLevel = "standard"
    risk_tolerance: float = Field(default=0.6, ge=0, le=1)
    negotiation_style: str = "analytical but cooperative"
    hidden_priority: str = "control total cost while securing strong warranty protection"


class SellerConfig(BaseModel):
    target_price: float = 112000
    minimum_acceptable_price: float = 87000
    preferred_delivery_days: int = 35
    minimum_delivery_days: int = 14
    preferred_contract_months: int = 24
    preferred_warranty: WarrantyLevel = "standard"
    risk_tolerance: float = Field(default=0.55, ge=0, le=1)
    negotiation_style: str = "firm, transparent, and value-oriented"
    hidden_priority: str = "protect margin and avoid short contracts with extended warranty"


class NegotiationConfig(BaseModel):
    buyer: BuyerConfig = Field(default_factory=BuyerConfig)
    seller: SellerConfig = Field(default_factory=SellerConfig)
    max_rounds: int = Field(default=8, ge=2, le=50)
    provider: str = "mock"
    model_name: str = "mock-negotiator-v1"
    scenario: str = "Cloud GPU capacity contract for a mid-market AI platform team."


class AgentResponse(BaseModel):
    message: str
    offer: Offer
    visible_reasoning_summary: str
    accept: bool = False
    walk_away: bool = False

    @field_validator("message", "visible_reasoning_summary")
    @classmethod
    def no_private_goal_language(cls, value: str) -> str:
        banned = ["hidden_priority", "maximum_acceptable", "minimum_acceptable"]
        lowered = value.lower()
        if any(term in lowered for term in banned):
            raise ValueError("agent output appears to expose private configuration names")
        return value


class TranscriptEntry(BaseModel):
    round_number: int
    agent: AgentRole
    message: str
    offer: Offer
    visible_reasoning_summary: str
    concession_explanation: str | None = None
    accept: bool
    walk_away: bool


class UtilityScore(BaseModel):
    buyer: float = Field(ge=0, le=100)
    seller: float = Field(ge=0, le=100)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    approximate_cost_usd: float | None = None


class ProviderRunInfo(BaseModel):
    requested_provider: str = "mock"
    active_provider: str = "mock"
    model_name: str = "mock-negotiator-v1"
    fallback_reason: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


class TraceEvent(BaseModel):
    index: int
    event_type: str
    detail: str
    actor: AgentRole | None = None


class NegotiationState(BaseModel):
    negotiation_id: str = Field(default_factory=lambda: str(uuid4()))
    status: NegotiationStatus = NegotiationStatus.CONFIGURED
    config: NegotiationConfig
    current_round: int = 0
    latest_offer: Offer | None = None
    transcript: list[TranscriptEntry] = Field(default_factory=list)
    utility_history: list[UtilityScore] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    provider_info: ProviderRunInfo = Field(default_factory=ProviderRunInfo)
    outcome_summary: str | None = None


class StartNegotiationRequest(BaseModel):
    config: NegotiationConfig = Field(default_factory=NegotiationConfig)


class ProviderRuntimeConfig(BaseModel):
    requested_provider: str = "mock"
    active_provider: str = "mock"
    model_name: str = "mock-negotiator-v1"
    api_key: str | None = None
    fallback_reason: str | None = None
