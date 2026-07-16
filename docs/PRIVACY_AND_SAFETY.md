# Privacy and safety

SpeechShift implements the workspace content and safety policy with these controls:

- no account or personal details;
- microphone inactive until the visitor explicitly grants permission and holds the record control;
- permission-check streams stop immediately, while recording streams stop on release, limit, cancellation, device loss, reset or page exit;
- Replay keeps microphone samples and playback WAVs in browser memory only;
- Local DSP and Mock contract send bounded PCM to the loopback SpeechShift backend for in-memory processing, then clear it on completion, cancellation or reset;
- no audio or transcript persistence;
- storage and transcript logging settings are rejected when enabled;
- non-identifying technical logs only;
- immediate mute, cancel and reset;
- safe output volume capped at 85%, with a default of 75%;
- short curated sentences and no open-ended conversation;
- only non-identifying synthetic voice styles;
- replay and prepared timing labelled in the visitor UI;
- errors and limitations stated without claiming human-like understanding.

Reset stops microphone capture and output, revokes the local recording URL, cancels active work, invalidates stale events and deletes the server session. Shutdown clears all remaining in-memory sessions.

Recommended sign:

> This demonstration processes your voice during a live interaction and clears it when the session resets. Please do not say private information. Generated voices and translations may contain errors. Replay mode uses prepared audio and does not activate the microphone.
