# ModelDeck capability contract

Status: proposed production contract; deterministic development mock implemented in SpeechShift. ModelDeck itself does not yet expose a speech route.

SpeechShift will connect only to `http://127.0.0.1:8600` and never to management or worker ports. WebSockets are the preferred initial transport because the visitor contract needs bidirectional binary audio, cancellation, partial text and streamed audio.

## `speech.voice_transform`

The opening JSON message contains `session_id`, `profile`, `source_language`, and an audio format fixed initially to mono `pcm_s16le` at 16 kHz. Subsequent binary input frames have sequence numbers and bounded buffering. Client end-of-input and cancellation are explicit.

Output events include:

- `state` (`receiving_audio`, `processing`, `generating_audio`);
- sequenced binary `audio` frames;
- `metrics` with input duration, first-audio latency and underruns;
- structured `error` with stable code, recoverability and public-safe detail;
- `complete`.

## `speech.translate`

The opening message additionally contains `target_language` and a safe `voice_profile`. Output adds `transcript_partial`, `transcript_final`, `translation_partial` where supported, and `translation_final` before generated audio.

## Protocol invariants

- bounded input and output buffers;
- monotonically increasing sequence numbers;
- stale-session rejection;
- one terminal `complete`, `cancelled` or `error` event;
- cancellation reflected promptly and acknowledged;
- no transcript text in technical gateway logs;
- structured not-ready, unsupported-language and invalid-profile errors;
- gateway disconnect does not trigger a silent provider change.

## Implemented mock framing

The development mock uses the SpeechShift session WebSocket until ModelDeck owns a real gateway route. A `start_mock` JSON message declares the mode, curated selection and audio format. Each subsequent binary input message begins with a four-byte little-endian sequence number followed by PCM16 audio. `end_audio` closes input.

Output sends `audio_start` JSON with the audio format, sequenced binary PCM16 messages, then `audio_end`. Input and output reject missing, repeated or out-of-order frames and enforce hard byte limits. Cancellation clears pending input and stops output. This framing is evidence for the proposed contract, not a commitment that ModelDeck must reuse the development route name.

The initial capability should be one composite speech worker if physical probes show it improves cancellation and GPU-memory coordination. Multiple workers are justified only if independent lifecycle or reuse demonstrably outweighs extra hops and scheduling complexity.
