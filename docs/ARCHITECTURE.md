# Architecture

## Decision

SpeechShift uses a local browser UI with a Python orchestration backend. A browser is the lower-risk choice for a large-screen, kiosk-style stage visualisation and future bidirectional ModelDeck streaming. FastAPI serves the compiled TypeScript bundle so Open Day operation needs one process and one demo-owned port.

PySide6 remains proven for VoiceChanger's direct DSP path, but using it here would couple browser-quality layout, audio streaming and staff recovery to a larger desktop widget implementation. Browser microphone device labels still require permission and output-device selection support varies, so Phase 2 must be tested on the event browser and Fedora image.

## Components

- `frontend/`: visitor experience, provider visibility, output mute/playback, stage animation and staff diagnostics.
- `frontend/src/audio.ts`: explicit microphone permission, device discovery, bounded AudioWorklet capture, input-level monitoring, resampling and in-memory WAV encoding.
- `frontend/public/audio-worklet.js`: low-latency mono sample frames sent only to the browser UI thread.
- `backend/speechshift/config.py`: fail-fast runtime and privacy validation.
- `sessions.py`: bounded, memory-only sessions with cancellation and reset generations.
- `replay.py`: deterministic provider and catalogue validation.
- `modeldeck.py`: gateway-only readiness checks and staged STT, translation and TTS orchestration.
- `main.py`: HTTP/WebSocket API and local static serving.
- `assets/replay/`: approved prepared metadata and audio.

## Provider boundary

The interface is intentionally explicit:

- `replay`: implemented and ready without a live model;
- `mock-modeldeck`: development-only contract simulator with no model;
- `local`: implemented in development as a real SpeechShift-owned DSP baseline; it is not an AI model;
- `modeldeck`: development-only live pipeline, selectable only while all required gateway routes report ready.

There is no automatic provider switching. Future fallback requires a visible staff action. A live provider failure must not mutate the configured provider.

Staff can explicitly switch providers without restarting the UI. Local DSP, Mock and ModelDeck are rejected outside development mode. ModelDeck selection returns a structured not-ready response unless `speechshift-stt`, `speechshift-en-fr`, `speechshift-en-de` and `speechshift-voice` are all ready. A readiness loss blocks new live runs without changing the selected provider.

## ModelDeck pipeline

SpeechShift accepts the visitor's bounded sequenced PCM stream on its own session WebSocket, then calls only the ModelDeck gateway at `127.0.0.1:8600`. It submits mono PCM16 audio to `speechshift-stt`, optionally sends recognised text to the selected French or German translation route, and sends the final text to `speechshift-voice`. Voice Shift offers the curated built-in speakers Ryan, Aiden, Vivian and Serena; Language Shift continues to use Ryan. The UI labels recognition, translation and generation as asynchronous stages rather than claiming live streaming.

Each gateway stage has a hard timeout and the complete pipeline has a 110-second timeout. Cancellation, reset, timeout and failed output validation forward request cancellation to the gateway and discard SpeechShift's in-memory buffers. Returned audio must be a bounded mono PCM16 24 kHz WAV before it is streamed to the browser.

## Local DSP baseline

Local DSP reuses only the narrow, proven algorithmic ideas inspected in VoiceChanger; SpeechShift has its own standard-library implementation and no VoiceChanger runtime dependency. It accepts the same bounded sequenced PCM stream as the mock contract and returns the visitor's actually processed audio:

- Calm DSP slightly lowers pitch, slows delivery and smooths high-frequency variation.
- Energetic DSP slightly raises pitch, speeds delivery and applies bounded drive.
- Artificial robot DSP applies 30 Hz ring modulation.
- Anonymised voice applies a fixed McAdams coefficient to short-frame LPC pole
  angles, reshaping formant emphasis without changing the recording duration.

Every profile applies an 82% sample ceiling and short start/end fades. Local DSP does not recognise or regenerate words and cannot provide Language Shift. The visitor UI hides recognition stages and explicitly describes this as signal processing rather than AI. Its request contains only the selected DSP profile and audio format: there is no sentence identifier because the captured recording is the input. The UI therefore shows **Your recording** instead of the replay fixture chooser.

The anonymised profile is an independent standard-library implementation of
the McAdams-coefficient technique used by the
[VoicePrivacy B2 baseline](https://github.com/Voice-Privacy-Challenge/Voice-Privacy-Challenge-2026).
It has
no model, checkpoint, network access, transcript, real speaker identifier or
target recording. The profile is deterministic and intended as an experimental
privacy treatment, not proof that a speaker cannot be re-identified. It remains
development-only until the same synthetic-corpus privacy and intelligibility
gates used for model candidates have been measured.

## Session lifecycle

Create → connect WebSocket → start → stream sequenced events → complete/cancel → delete/reset. Every event carries a session generation and sequence. The UI rejects old generations and repeated sequences. Session buffers are bounded and cleared on reset or shutdown.

## Local audio lifecycle

Microphone capture is intentionally independent of the replay provider:

1. The visitor explicitly grants browser permission. The permission-check stream is stopped immediately.
2. Available input labels are shown and one device is selected.
3. Holding the record control opens a new mono input stream and AudioWorklet.
4. Frames enter a hard-bounded buffer sized from the actual device sample rate and configured duration limit.
5. Release, the duration limit, cancellation or device loss stops tracks and closes the audio context.
6. A completed recording is resampled to mono 16 kHz PCM and encoded as an in-memory WAV for local playback.
7. Clear, reset or page exit revokes the object URL and discards the samples.
8. Once visitor data or a backend session exists, deliberate pointer or keyboard activity renews a bounded idle timer. A visible warning appears before expiry; expiry reuses the full reset path to stop capture and playback, revoke audio URLs, clear text and delete the backend session without changing provider.

Replay mode keeps every microphone frame and WAV in the browser. Local DSP, Mock contract and ModelDeck add an explicit transport step: mono 16 kHz PCM16 is divided into sequenced binary frames, sent with backpressure over the session WebSocket and accumulated in a backend buffer capped at eight seconds. Output paths use the same sequenced binary framing in reverse. The browser rebuilds a memory-only WAV and revokes it on reset.

The mock emits deterministic partial/final text and prepared audio fixtures. Every event carries `mock: true`; fixture text and mock timing are additionally labelled. It validates integration behaviour but provides no evidence that a speech model works.

## Port status

`3800` is a development proposal, not a confirmed exact OpenDayOps assignment. Open Day start-up is gated by explicit allocation confirmation. Required OpenDayOps changes are:

1. add `SpeechShift` application port `3800` to `PORTS_AND_LOCAL_SERVICES.md`;
2. add the allocation decision to `DECISIONS_LOG.md`;
3. add the visitor and health URLs to the runbook and staff URL sheet;
4. add SpeechShift to whole-stack port smoke testing.
