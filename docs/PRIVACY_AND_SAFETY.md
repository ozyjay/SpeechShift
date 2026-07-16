# Privacy and safety

SpeechShift implements the workspace content and safety policy with these controls:

- no account or personal details;
- microphone inactive until an explicit future visitor action;
- no audio or transcript persistence;
- storage and transcript logging settings are rejected when enabled;
- non-identifying technical logs only;
- immediate mute, cancel and reset;
- safe output volume capped at 85%, with a default of 75%;
- short curated sentences and no open-ended conversation;
- only non-identifying synthetic voice styles;
- replay and prepared timing labelled in the visitor UI;
- errors and limitations stated without claiming human-like understanding.

Reset stops output, cancels active work, invalidates stale events and deletes the server session. Shutdown clears all remaining in-memory sessions.

Recommended sign:

> This demonstration processes your voice during a live interaction and clears it when the session resets. Please do not say private information. Generated voices and translations may contain errors. Replay mode uses prepared audio and does not activate the microphone.

