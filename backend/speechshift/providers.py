from __future__ import annotations

from speechshift.config import DemoMode, SpeechProvider


class ProviderSelectionError(ValueError):
    pass


class ProviderRegistry:
    def __init__(
        self, initial: SpeechProvider, demo_mode: DemoMode, *, modeldeck_ready: bool = False
    ) -> None:
        self._selected = initial
        self._demo_mode = demo_mode
        self._modeldeck_ready = modeldeck_ready

    def set_modeldeck_ready(self, ready: bool) -> None:
        self._modeldeck_ready = ready

    @property
    def selected(self) -> SpeechProvider:
        return self._selected

    @property
    def label(self) -> str:
        return {
            SpeechProvider.REPLAY: "Replay mode",
            SpeechProvider.MOCK_MODELDECK: "Mock contract",
            SpeechProvider.LOCAL: "Local DSP",
            SpeechProvider.MODELDECK: "ModelDeck",
        }[self._selected]

    def statuses(self) -> list[dict[str, str]]:
        mock_state = "ready" if self._demo_mode is DemoMode.DEVELOPMENT else "development-only"
        local_state = "ready" if self._demo_mode is DemoMode.DEVELOPMENT else "development-only"
        return [
            {"id": "replay", "label": "Replay", "state": "ready", "detail": "Prepared offline examples"},
            {
                "id": "mock-modeldeck",
                "label": "Mock contract",
                "state": mock_state,
                "detail": "Deterministic binary-stream integration; no AI model",
            },
            {
                "id": "local",
                "label": "Local DSP",
                "state": local_state,
                "detail": "Real offline voice effects; signal processing, not AI",
            },
            {
                "id": "modeldeck",
                "label": "ModelDeck",
                "state": "ready" if self._modeldeck_ready else "not-configured",
                "detail": (
                    "Live local STT, translation and synthetic speech"
                    if self._modeldeck_ready
                    else "Requires four ready SpeechShift routes in the local gateway"
                ),
            },
        ]

    def select(self, requested: str) -> SpeechProvider:
        try:
            provider = SpeechProvider(requested)
        except ValueError as error:
            raise ProviderSelectionError("unknown provider") from error
        if provider is SpeechProvider.MOCK_MODELDECK and self._demo_mode is not DemoMode.DEVELOPMENT:
            raise ProviderSelectionError("mock provider is development-only")
        if provider is SpeechProvider.LOCAL and self._demo_mode is not DemoMode.DEVELOPMENT:
            raise ProviderSelectionError("local DSP provider is development-only")
        if provider is SpeechProvider.MODELDECK:
            if self._demo_mode is not DemoMode.DEVELOPMENT:
                raise ProviderSelectionError("modeldeck provider is development-only")
            if not self._modeldeck_ready:
                raise ProviderSelectionError("provider is not ready")
        self._selected = provider
        return provider
