from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ShiftMode(StrEnum):
    VOICE = "voice"
    LANGUAGE = "language"


class ReplayRunRequest(BaseModel):
    mode: ShiftMode
    sentence_id: str = Field(min_length=1, max_length=64)
    selection_id: str = Field(min_length=1, max_length=64)


class AudioFormat(BaseModel):
    encoding: str
    sample_rate_hz: int = Field(ge=8_000, le=48_000)
    channels: int = Field(ge=1, le=2)


class MockRunRequest(ReplayRunRequest):
    audio_format: AudioFormat


class LocalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: str = Field(min_length=1, max_length=64)
    audio_format: AudioFormat


class ProviderSelection(BaseModel):
    provider: str


class SessionCreated(BaseModel):
    session_id: str
    generation: int


class ProviderStatus(BaseModel):
    id: str
    label: str
    state: str
    detail: str


class LocalVoiceProfile(BaseModel):
    id: str
    label: str
    description: str


class PublicConfig(BaseModel):
    demo_name: str
    demo_mode: str
    provider: str
    provider_label: str
    audio_sample_rate: int
    max_input_seconds: int
    visitor_idle_timeout_seconds: int
    safe_output_volume: float
    port_allocation_confirmed: bool
    providers: list[ProviderStatus]
    local_voice_profiles: list[LocalVoiceProfile]
