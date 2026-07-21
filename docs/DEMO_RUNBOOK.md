# Demo runbook

## Before opening

1. Confirm headphones are connected, select them under **Operator controls → Playback output**, play both an original microphone check and a prepared result, and confirm the output volume is comfortable. If browser output selection is unavailable, select the booth device in system settings and confirm the operator diagnostic reports that limitation.
2. Run `scripts/start_dev.ps1` until OpenDayOps formally allocates the port; after allocation use `scripts/start_openday.ps1` with the required confirmation setting.
3. Open `http://127.0.0.1:3800` and run `scripts/smoke_test.ps1`.
4. Grant microphone permission, choose the booth microphone, record a short local check and confirm the level meter and playback.
5. Clear that check, then play one Voice Shift and one Language Shift result.
6. Confirm the header says **Replay mode**, the microphone is inactive outside recording, and reset clears both local and replay audio.

## Visitor script

“You can check your microphone locally; that recording stays in browser memory. The transformation is still a prepared run showing the stages a live speech system uses. Generated voices and translations are approximations and can be wrong.”

## Between visitors

Select **Next visitor / Reset**. Confirm microphone capture and playback stop, the local recording is unavailable, the journey returns to waiting, and the staff session diagnostic says cleared.

If visitor data is left unattended, a privacy warning appears 15 seconds before the configured inactivity timeout. Pointer or keyboard activity keeps the session active; otherwise SpeechShift performs the same reset automatically without changing the selected provider.

## Recovery

- Sound problem: select mute, check headphones, then reset.
- Output disconnected: open **Operator controls**, confirm the output warning, choose the replacement device and replay a result. SpeechShift visibly returns to the system default when the selected output disappears.
- Sequence stuck: select cancel, then reset. Refresh the browser if necessary.
- Application unavailable: restart only SpeechShift after confirming port `3800` is free.
- ModelDeck unavailable: no action is needed for replay; do not present a live provider as active.

## Development mock check

Open **Operator controls** and explicitly choose **Mock contract**. Record a short sample, then select **Run mock pipeline**. Explain that the input transport is real but the transcript, translation, timing and output audio are deterministic fixtures. Return the provider to **Replay** before public operation. Mock contract is rejected in Open Day mode.

## Local DSP check

Open **Operator controls** and choose **Local DSP**. Record the curated sentence, select each voice profile and use **Apply local voice shift**. Confirm output is clear, bounded and recognisably changed. Explain that this baseline uses ordinary signal processing rather than AI. Language Shift is deliberately unavailable. Return to **Replay** before public operation until Local DSP passes event acceptance.

For **Anonymised voice**, also confirm that output duration matches the input.
Describe it as an experimental formant-shifting privacy treatment, not a
guarantee of anonymity. It uses no transcript, target voice or model download.

## Shutdown

Reset the active session, close the browser and interrupt the foreground SpeechShift process. If it is detached, use `scripts/stop.ps1`, which refuses to stop a process that does not identify as SpeechShift. Application shutdown clears remaining in-memory sessions.
