# SpeechShift

SpeechShift is a standalone, local-first Open Day demonstration of AI-produced speech transformation.

> Speak once. Hear your words in another voice—or another language.

This first production milestone is an honest replay-first MVP. It presents prepared synthetic audio through the complete visitor story without requiring a microphone, internet connection, model download or ModelDeck. It does not pretend that a live model processed visitor speech.

## What works now

- Voice Shift with three non-identifying synthetic styles.
- Language Shift to French or German.
- Three curated source sentences and prepared local WAV output.
- Deterministic WebSocket stage events, cancellation and stale-session rejection.
- Explicit `Replay mode` labelling and prepared-timing labelling.
- One-click reset that stops playback and clears the in-memory session.
- Immediate output mute and a safe volume ceiling.
- Unified visitor screen and staff diagnostics panel.
- Strict privacy and ModelDeck gateway configuration checks.

The microphone is deliberately inactive in this milestone. The `local` and `modeldeck` providers are visible but unavailable until their implementation and readiness gates pass.

## Quick start

Requires Python 3.12+, Node.js 22+ and PowerShell 7 on Fedora 44.

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
Replay assets (current) | local (future) | ModelDeck gateway :8600 (future)
```

SpeechShift never calls ModelDeck management or worker ports. See [Architecture](docs/ARCHITECTURE.md), [privacy and safety](docs/PRIVACY_AND_SAFETY.md), and the [demo runbook](docs/DEMO_RUNBOOK.md).

## OpenDayOps authorities

Workspace-wide exact ports, public content policy and operating policy remain authoritative in:

- `OpenDayOps/PORTS_AND_LOCAL_SERVICES.md`
- `OpenDayOps/CONTENT_AND_SAFETY_GUIDE.md`
- `OpenDayOps/DEMO_RUNBOOK.md`

SpeechShift documents how it implements those policies without duplicating their full contents.
