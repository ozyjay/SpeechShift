from pathlib import Path

import pytest
from pydantic import ValidationError
from speechshift.config import Settings


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "replay_asset_dir": Path("assets/replay"),
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_safe_development_defaults_are_memory_only() -> None:
    value = settings()
    assert value.speech_provider == "replay"
    assert value.store_visitor_audio is False
    assert value.log_transcripts is False


@pytest.mark.parametrize(
    ("key", "value"),
    [("store_visitor_audio", True), ("log_transcripts", True)],
)
def test_rejects_persistent_visitor_data(key: str, value: object) -> None:
    with pytest.raises(ValidationError, match="not supported"):
        settings(**{key: value})


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:3600",
        "http://127.0.0.1:8610",
        "https://127.0.0.1:8600",
        "http://example.org:8600",
    ],
)
def test_rejects_non_gateway_modeldeck_urls(url: str) -> None:
    with pytest.raises(ValidationError, match="ModelDeck gateway|MODELDECK_URL"):
        settings(modeldeck_url=url)


def test_open_day_requires_confirmed_allocation() -> None:
    with pytest.raises(ValidationError, match="confirmed OpenDayOps port"):
        settings(demo_mode="openday")


def test_open_day_rejects_unrehearsed_live_provider() -> None:
    with pytest.raises(ValidationError, match="no rehearsed live provider"):
        settings(demo_mode="openday", port_allocation_confirmed=True, speech_provider="modeldeck")

