# Test plan

## Automated now

- strict configuration and privacy rejection;
- ModelDeck gateway URL enforcement;
- Open Day port-allocation gate;
- bounded session eviction and reset cancellation;
- replay catalogue completeness and asset presence;
- deterministic event ordering and sequencing;
- cancellation before replay emission;
- API health truthfulness and structured invalid-request errors;
- frontend stale-event rejection and honest latency labelling;
- inactivity warning, activity renewal and automatic visitor-data clearing without provider changes;
- explicit output-device discovery and routing of both playback players;
- hard-bounded audio frame buffering;
- deterministic 48 kHz to 16 kHz resampling shape;
- mono 16-bit PCM WAV encoding;
- sequenced PCM input/output framing and ordering rejection;
- backend byte-buffer limits and short-audio rejection;
- shared PCM silence rejection before mock or Local DSP processing;
- explicit development provider selection, four-route ModelDeck readiness and unavailable live-provider rejection;
- staged ModelDeck STT, translation and TTS request contracts, event ordering, bounded WAV validation and cancellation on failure;
- exact Ryan, Aiden, Vivian and Serena ModelDeck voice allowlisting with unsupported speakers rejected before gateway traffic;
- deterministic mock partial/final events, binary fixture output and metrics;
- Local DSP profile validation, duration changes, amplitude ceiling, fades and real transformed binary output;
- deterministic local anonymisation, duration preservation and rejection of target-voice fields;
- Local DSP request and interface contain no replay sentence semantics;
- model checkpoint licence audit blocks downloads unless every declared artefact is reviewed;
- isolated TTS completion, generation cancellation, hard start-up and generation timeouts, worker-process exit and sanitised worker errors;
- TTS burn-in sequencing, hot-start refusal, active GPU/CPU thermal cut-offs and sysfs temperature/VRAM sensor discovery;
- voice-transform readiness thresholds, schema-version compatibility and a twelve-clip in-memory synthetic eSpeak harness;
- TypeScript type-check, production build, Python lint and tests;
- headless system-Chromium smoke across every replay combination, local-only anonymisation selection, provider-specific source semantics, audio loading and visitor reset.

## Operational now

- `scripts/smoke_test.ps1` checks a running application's health and catalogue;
- the smoke test exercises Mock contract and Local DSP with synthetic sequenced PCM, validates events, binary ordering and changed DSP output, then restores Replay;
- `scripts/burn_in.ps1` performs repeated create/reset cycles;
- manually verify microphone permission denial and approval, input and output device selection, live level, hold/release capture, eight-second auto-stop, original and result playback through the selected output, mute, clear, reset, browser refresh and input/output unplug/replug;
- manually verify both transformation modes, all 18 replay WAV files, cancel, reset and staff panel at the event resolution;
- perform a 60-minute replay loop and inspect memory before promotion.

## Required for later live milestones

Test gateway restart/disconnect, binary frame order and backpressure, cancellation latency, model memory release, Vivian and Serena pronunciation across English, French and German, 50-session live reset, 60-minute live burn-in and whole-stack GPU/port coexistence.
