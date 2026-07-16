from __future__ import annotations

from speechshift.config import DemoMode, SpeechProvider


class ProviderSelectionError(ValueError):
    pass


class ProviderRegistry:
    def __init__(self, initial: SpeechProvider, demo_mode: DemoMode) -> None:
        self._selected = initial
        self._demo_mode = demo_mode

    @property
    def selected(self) -> SpeechProvider:
        return self._selected

    @property
    def label(self) -> str:
        return {
            SpeechProvider.REPLAY: "Replay mode",
            SpeechProvider.MOCK_MODELDECK: "Mock contract",
            SpeechProvider.LOCAL: "Local provider",
            SpeechProvider.MODELDECK: "ModelDeck",
        }[self._selected]

    def statuses(self) -> list[dict[str, str]]:
        mock_state = "ready" if self._demo_mode is DemoMode.DEVELOPMENT else "development-only"
        return [
            {"id": "replay", "label": "Replay", "state": "ready", "detail": "Prepared offline examples"},
            {
                "id": "mock-modeldeck",
                "label": "Mock contract",
                "state": mock_state,
                "detail": "Deterministic binary-stream integration; no AI model",
            },
            {"id": "local", "label": "Local", "state": "not-configured", "detail": "Model spike pending"},
            {
                "id": "modeldeck",
                "label": "ModelDeck",
                "state": "not-configured",
                "detail": "Speech capability does not yet exist in the gateway",
            },
        ]

    def select(self, requested: str) -> SpeechProvider:
        try:
            provider = SpeechProvider(requested)
        except ValueError as error:
            raise ProviderSelectionError("unknown provider") from error
        if provider is SpeechProvider.MOCK_MODELDECK and self._demo_mode is not DemoMode.DEVELOPMENT:
            raise ProviderSelectionError("mock provider is development-only")
        if provider in {SpeechProvider.LOCAL, SpeechProvider.MODELDECK}:
            raise ProviderSelectionError("provider is not ready")
        self._selected = provider
        return provider

