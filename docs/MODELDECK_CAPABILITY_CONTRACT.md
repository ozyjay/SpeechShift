# ModelDeck capability contract

Status: implemented in SpeechShift and ModelDeck; live availability remains fail-closed on all four routes reporting ready.

SpeechShift connects only to the ModelDeck gateway at `http://127.0.0.1:8600`. It never calls management or worker ports. The provider is development-only and remains unavailable until `GET /v1/routes` reports all four API model IDs ready:

- `speechshift-stt` using `speech-recognition-v1`;
- `speechshift-en-fr` using English-to-French translation;
- `speechshift-en-de` using English-to-German translation;
- `speechshift-voice` using speech synthesis.

These are API model IDs, not protocol-contract names. ModelDeck route configuration maps each unique API model ID to its compatible protocol contract and worker order.

## Recognition

`POST /v1/audio/transcriptions` receives JSON containing a request ID, model `speechshift-stt`, language `en`, and base64-encoded mono `pcm_s16le` audio at 16 kHz. SpeechShift accepts at most eight seconds and expects a non-empty `text` response. ModelDeck implements this route under `speech-recognition-v1` and keeps the decoded audio and transcript in memory only.

## Translation

`POST /v1/translations` receives recognised text, source language `en`, target `fr` or `de`, and the matching translation API model ID. SpeechShift expects non-empty `output_text`. Voice Shift skips this stage.

## Speech synthesis

`POST /v1/audio/speech` receives the final text, model `speechshift-voice`, response format `wav`, and a curated voice. Voice Shift permits the built-in speakers Ryan, Aiden, Vivian or Serena; Language Shift uses Ryan. SpeechShift accepts at most 2 MB and validates mono PCM16 at 24 kHz before forwarding audio.

## Runtime invariants

- readiness is fail-closed and requires every route;
- input is bounded sequenced PCM and silent input is rejected before ModelDeck;
- stage and whole-pipeline timeouts are hard limits;
- cancellation is forwarded through `POST /v1/requests/{request_id}/cancel`;
- audio and transcript text are never written to SpeechShift logs;
- errors are structured and do not silently change provider;
- visitor audio, text and generated output remain in memory and are cleared on cancellation, reset, timeout and shutdown.

The SpeechShift WebSocket remains its browser-facing transport. A `start_modeldeck` message declares the mode, selection and audio format; sequenced binary input follows, then `end_audio`. Output uses staged JSON events plus sequenced binary PCM frames. This keeps browser session lifecycle and stale-generation protection owned by SpeechShift while ModelDeck owns model routing and execution.
