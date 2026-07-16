from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ShiftMode(StrEnum):
    VOICE = "voice"
    LANGUAGE = "language"


class ReplayRunRequest(BaseModel):
    mode: ShiftMode
    sentence_id: str = Field(min_length=1, max_length=64)
    selection_id: str = Field(min_length=1, max_length=64)


class SessionCreated(BaseModel):
    session_id: str
    generation: int


class ProviderStatus(BaseModel):
    id: str
    label: str
    state: str
    detail: str


class PublicConfig(BaseModel):
    demo_name: str
    demo_mode: str
    provider: str
    provider_label: str
    max_input_seconds: int
    safe_output_volume: float
    port_allocation_confirmed: bool
    providers: list[ProviderStatus]

