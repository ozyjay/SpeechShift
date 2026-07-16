# ModelDeck capability contract

Status: proposed; not implemented by this replay-first milestone.

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

The initial capability should be one composite speech worker if physical probes show it improves cancellation and GPU-memory coordination. Multiple workers are justified only if independent lifecycle or reuse demonstrably outweighs extra hops and scheduling complexity.

