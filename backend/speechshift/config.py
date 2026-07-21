from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DemoMode(StrEnum):
    DEVELOPMENT = "development"
    OPEN_DAY = "openday"


class SpeechProvider(StrEnum):
    REPLAY = "replay"
    MOCK_MODELDECK = "mock-modeldeck"
    LOCAL = "local"
    MODELDECK = "modeldeck"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    demo_name: str = "SpeechShift"
    demo_mode: DemoMode = DemoMode.DEVELOPMENT
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=3800, ge=1, le=65535)
    port_allocation_confirmed: bool = False
    speech_provider: SpeechProvider = SpeechProvider.REPLAY
    modeldeck_url: str = "http://127.0.0.1:8600"
    audio_sample_rate: int = Field(default=16_000, ge=8_000, le=48_000)
    audio_channels: int = Field(default=1, ge=1, le=2)
    max_input_seconds: int = Field(default=8, ge=1, le=15)
    visitor_idle_timeout_seconds: int = Field(default=120, ge=30, le=900)
    safe_output_volume: float = Field(default=0.75, ge=0.0, le=0.85)
    replay_asset_dir: Path = Path("assets/replay")
    store_visitor_audio: bool = False
    log_transcripts: bool = False

    @model_validator(mode="after")
    def validate_safety_and_runtime(self) -> Settings:
        if self.store_visitor_audio:
            raise ValueError("visitor audio storage is not supported")
        if self.log_transcripts:
            raise ValueError("transcript logging is not supported")
        if self.app_host not in {"127.0.0.1", "localhost"}:
            raise ValueError("SpeechShift must bind to a loopback address")

        parsed = urlparse(self.modeldeck_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("MODELDECK_URL must use the local ModelDeck gateway")
        if parsed.port != 8600 or parsed.path not in {"", "/"}:
            raise ValueError("MODELDECK_URL must point to the gateway at http://127.0.0.1:8600")

        if self.demo_mode is DemoMode.OPEN_DAY:
            if not self.port_allocation_confirmed:
                raise ValueError("Open Day mode requires a confirmed OpenDayOps port allocation")
            if self.app_port != 3800:
                raise ValueError("Open Day mode requires the confirmed SpeechShift port")
            if self.speech_provider is not SpeechProvider.REPLAY:
                raise ValueError("this release has no rehearsed live provider; select replay")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
