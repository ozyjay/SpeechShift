# SpeechShift

SpeechShift is a standalone, local-first Open Day demonstration of AI-produced speech transformation.

> Speak once. Hear your words in another voice—or another language.

SpeechShift is an honest replay-first MVP with a separate local microphone foundation. It presents prepared synthetic audio through the complete visitor story without requiring a microphone, internet connection, model download or ModelDeck. Visitors may explicitly enable a memory-only microphone check to record and replay their original voice, but the interface does not pretend that the prepared transformation processed it.

## What works now

- Voice Shift with three non-identifying synthetic styles.
- Language Shift to French or German.
- Three curated source sentences and prepared local WAV output.
- Deterministic WebSocket stage events, cancellation and stale-session rejection.
- Explicit `Replay mode` labelling and prepared-timing labelling.
- One-click reset that stops playback and clears the in-memory session.
- Immediate output mute and a safe volume ceiling.
- Explicit microphone permission and input-device selection.
- Operator-selectable playback output with visible browser-support and disconnect diagnostics.
- Hold-to-record capture with an eight-second hard limit and live input-level meter.
- Mono 16 kHz PCM conversion and local original-audio playback entirely in browser memory.
- Microphone unplug handling and recording cleanup on cancel, reset and page exit.
- A visible inactivity warning followed by automatic visitor-data clearing.
- Staff-selectable deterministic mock contract in development mode.
- Sequenced, bounded binary PCM input and output over the session WebSocket.
- Partial/final transcript events, translation events, streamed output audio, cancellation and structured errors.
- Real offline Local DSP Voice Shift for captured visitor audio.
- Development-only ModelDeck orchestration for live recognition, French/German translation and synthetic speech.
- Fail-closed ModelDeck readiness requiring all four API model IDs before staff can select it.
- Calm, energetic and clearly artificial robot DSP profiles with limiting and click-reducing fades.
- Unified visitor screen and staff diagnostics panel.
- Strict privacy and ModelDeck gateway configuration checks.

The microphone remains inactive until the visitor selects **Enable microphone** and then holds **Hold to record**. Releasing the button stops capture. In Replay mode, the recording never leaves the browser. Staff may explicitly select **Local DSP** in development mode to transform the real captured voice with offline signal processing. This baseline does not recognise words, translate speech or use an AI model. **Mock contract** remains available for deterministic integration testing.

The real **ModelDeck** provider becomes selectable in development only when the gateway reports `speechshift-stt`, `speechshift-en-fr`, `speechshift-en-de` and `speechshift-voice` ready. It runs those APIs as a visibly staged, asynchronous pipeline and never falls back to another provider. At present, ModelDeck still needs the proposed `speech-recognition-v1` route before this gate can pass.

## Quick start

Requires Python 3.12+, Node.js 22+, PowerShell 7 and system Chromium on Fedora 44. Set `SPEECHSHIFT_CHROMIUM` when Chromium is installed under a non-standard executable name or path.

```powershell
cp .env.example .env
pwsh -NoProfile -File scripts/setup.ps1
pwsh -NoProfile -File scripts/start_dev.ps1
```

Open <http://127.0.0.1:3800>. In another terminal, verify the running application:

```powershell
pwsh -NoProfile -File scripts/smoke_test.ps1
```

Port `3800` is a development proposal within the speech UI range reserved by OpenDayOps. It is not yet an exact operational allocation. `start_openday.ps1` refuses to start until the OpenDayOps registry has been updated and `PORT_ALLOCATION_CONFIRMED=true` is explicitly set.

## Development verification

```powershell
pwsh -NoProfile -File scripts/verify.ps1
```

The runtime serves the setup-generated frontend build from FastAPI. Node.js is used for setup, frontend development and verification, not while operating the demo. Freeze and verify that build with the rest of the event image before Open Day.

## Architecture

```text
Browser visitor/staff UI :3800 proposal
        ↕ HTTP + WebSocket
FastAPI orchestration and in-memory session state
        ↓ explicit provider
Replay assets | Local DSP baseline | mock contract | ModelDeck gateway :8600
```

SpeechShift never calls ModelDeck management or worker ports. See [Architecture](docs/ARCHITECTURE.md), [privacy and safety](docs/PRIVACY_AND_SAFETY.md), and the [demo runbook](docs/DEMO_RUNBOOK.md).

## OpenDayOps authorities

Workspace-wide exact ports, public content policy and operating policy remain authoritative in:

- `OpenDayOps/PORTS_AND_LOCAL_SERVICES.md`
- `OpenDayOps/CONTENT_AND_SAFETY_GUIDE.md`
- `OpenDayOps/DEMO_RUNBOOK.md`

SpeechShift documents how it implements those policies without duplicating their full contents.
