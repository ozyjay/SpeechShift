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


@pytest.mark.parametrize("provider", ["local", "modeldeck"])
def test_unready_live_providers_cannot_be_selected(provider: str) -> None:
    registry = ProviderRegistry(SpeechProvider.REPLAY, DemoMode.DEVELOPMENT)
    with pytest.raises(ProviderSelectionError, match="not ready"):
        registry.select(provider)

