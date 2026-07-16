# Demo runbook

## Before opening

1. Confirm headphones are connected and output volume is comfortable.
2. Run `scripts/start_dev.ps1` until OpenDayOps formally allocates the port; after allocation use `scripts/start_openday.ps1` with the required confirmation setting.
3. Open `http://127.0.0.1:3800` and run `scripts/smoke_test.ps1`.
4. Play one Voice Shift and one Language Shift result.
5. Confirm the header says **Replay mode**, the microphone says **off**, and reset clears the result.

## Visitor script

“This prepared run shows the same stages a live speech system uses. It recognises words, can translate their meaning, and generates new audio. The generated voice and translation are approximations and can be wrong.”

## Between visitors

Select **Next visitor / Reset**. Confirm playback stops, the journey returns to waiting, and the staff session diagnostic says cleared.

## Recovery

- Sound problem: select mute, check headphones, then reset.
- Sequence stuck: select cancel, then reset. Refresh the browser if necessary.
- Application unavailable: restart only SpeechShift after confirming port `3800` is free.
- ModelDeck unavailable: no action is needed for replay; do not present a live provider as active.

## Shutdown

Reset the active session, close the browser and interrupt the foreground SpeechShift process. If it is detached, use `scripts/stop.ps1`, which refuses to stop a process that does not identify as SpeechShift. Application shutdown clears remaining in-memory sessions.
