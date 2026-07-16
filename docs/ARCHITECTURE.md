# Architecture

## Decision

SpeechShift uses a local browser UI with a Python orchestration backend. A browser is the lower-risk choice for a large-screen, kiosk-style stage visualisation and future bidirectional ModelDeck streaming. FastAPI serves the compiled TypeScript bundle so Open Day operation needs one process and one demo-owned port.

PySide6 remains proven for VoiceChanger's direct DSP path, but using it here would couple browser-quality layout, audio streaming and staff recovery to a larger desktop widget implementation. Browser microphone device labels still require permission and output-device selection support varies, so Phase 2 must be tested on the event browser and Fedora image.

## Components

- `frontend/`: visitor experience, provider visibility, output mute/playback, stage animation and staff diagnostics.
- `backend/speechshift/config.py`: fail-fast runtime and privacy validation.
- `sessions.py`: bounded, memory-only sessions with cancellation and reset generations.
- `replay.py`: deterministic provider and catalogue validation.
- `main.py`: HTTP/WebSocket API and local static serving.
- `assets/replay/`: approved prepared metadata and audio.

## Provider boundary

The interface is intentionally explicit:

- `replay`: implemented and ready without a live model;
- `local`: reserved for repository-local model experiments, currently unavailable;
- `modeldeck`: reserved for the stable ModelDeck gateway, currently unavailable.

There is no automatic provider switching. Future fallback requires a visible staff action. A live provider failure must not mutate the configured provider.

## Session lifecycle

Create → connect WebSocket → start → stream sequenced events → complete/cancel → delete/reset. Every event carries a session generation and sequence. The UI rejects old generations and repeated sequences. Session buffers are bounded and cleared on reset or shutdown.

## Port status

`3800` is a development proposal, not a confirmed exact OpenDayOps assignment. Open Day start-up is gated by explicit allocation confirmation. Required OpenDayOps changes are:

1. add `SpeechShift` application port `3800` to `PORTS_AND_LOCAL_SERVICES.md`;
2. add the allocation decision to `DECISIONS_LOG.md`;
3. add the visitor and health URLs to the runbook and staff URL sheet;
4. add SpeechShift to whole-stack port smoke testing.

