import pytest
from speechshift.config import DemoMode, SpeechProvider
from speechshift.providers import ProviderRegistry, ProviderSelectionError


def test_mock_provider_is_explicit_and_development_only() -> None:
    development = ProviderRegistry(SpeechProvider.REPLAY, DemoMode.DEVELOPMENT)
    assert development.select("mock-modeldeck") is SpeechProvider.MOCK_MODELDECK
    assert development.label == "Mock contract"

    open_day = ProviderRegistry(SpeechProvider.REPLAY, DemoMode.OPEN_DAY)
    with pytest.raises(ProviderSelectionError, match="development-only"):
        open_day.select("mock-modeldeck")


def test_local_dsp_is_explicit_and_development_only() -> None:
    registry = ProviderRegistry(SpeechProvider.REPLAY, DemoMode.DEVELOPMENT)
    assert registry.select("local") is SpeechProvider.LOCAL
    assert registry.label == "Local DSP"

    open_day = ProviderRegistry(SpeechProvider.REPLAY, DemoMode.OPEN_DAY)
    with pytest.raises(ProviderSelectionError, match="development-only"):
        open_day.select("local")


def test_unready_modeldeck_provider_cannot_be_selected() -> None:
    registry = ProviderRegistry(SpeechProvider.REPLAY, DemoMode.DEVELOPMENT)
    with pytest.raises(ProviderSelectionError, match="not ready"):
        registry.select("modeldeck")
