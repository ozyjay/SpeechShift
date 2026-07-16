# Demo runbook

## Before opening

1. Confirm headphones are connected and output volume is comfortable.
2. Run `scripts/start_dev.ps1` until OpenDayOps formally allocates the port; after allocation use `scripts/start_openday.ps1` with the required confirmation setting.
3. Open `http://127.0.0.1:3800` and run `scripts/smoke_test.ps1`.
4. Grant microphone permission, choose the booth microphone, record a short local check and confirm the level meter and playback.
5. Clear that check, then play one Voice Shift and one Language Shift result.
6. Confirm the header says **Replay mode**, the microphone is inactive outside recording, and reset clears both local and replay audio.

## Visitor script

“You can check your microphone locally; that recording stays in browser memory. The transformation is still a prepared run showing the stages a live speech system uses. Generated voices and translations are approximations and can be wrong.”

## Between visitors

Select **Next visitor / Reset**. Confirm microphone capture and playback stop, the local recording is unavailable, the journey returns to waiting, and the staff session diagnostic says cleared.

## Recovery

- Sound problem: select mute, check headphones, then reset.
- Sequence stuck: select cancel, then reset. Refresh the browser if necessary.
- Application unavailable: restart only SpeechShift after confirming port `3800` is free.
- ModelDeck unavailable: no action is needed for replay; do not present a live provider as active.

## Development mock check

Open **Operator controls** and explicitly choose **Mock contract**. Record a short sample, then select **Run mock pipeline**. Explain that the input transport is real but the transcript, translation, timing and output audio are deterministic fixtures. Return the provider to **Replay** before public operation. Mock contract is rejected in Open Day mode.

## Shutdown

Reset the active session, close the browser and interrupt the foreground SpeechShift process. If it is detached, use `scripts/stop.ps1`, which refuses to stop a process that does not identify as SpeechShift. Application shutdown clears remaining in-memory sessions.
