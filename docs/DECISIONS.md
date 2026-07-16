# Decisions

## Accepted in this repository

- Use a local browser UI plus FastAPI orchestration backend.
- Serve the production UI from one process.
- Implement replay before microphone or live model work.
- Keep providers explicit and live providers unavailable until rehearsed.
- Use WebSockets and sequenced events as the transport foundation.
- Keep visitor data in memory only and reject persistence configuration.
- Validate microphone capture as a separate browser-only path before connecting it to any provider.
- Use AudioWorklet with a hard-bounded buffer and resample completed capture to mono 16 kHz PCM.
- Add `mock-modeldeck` as a development-only provider so the binary capability contract can be validated without misrepresenting ModelDeck readiness.
- Implement a dependency-free Local DSP Voice Shift baseline before selecting a speech model; label it as signal processing and keep Language Shift unavailable.
- Prefer one composite ModelDeck speech capability initially, subject to physical probes.

## Proposed externally

- Allocate exact SpeechShift application port `3800` in OpenDayOps. This is not accepted merely by appearing in this repository.

## Open

- Event browser and kiosk configuration.
- Headphones versus controlled speaker.
- Physical microphone and output device acceptance.
- Voice-conversion and multilingual model selection after ROCm/licence probes.
- Exact ModelDeck speech protocol route and binary framing.
