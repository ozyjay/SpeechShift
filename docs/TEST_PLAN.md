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
- hard-bounded audio frame buffering;
- deterministic 48 kHz to 16 kHz resampling shape;
- mono 16-bit PCM WAV encoding;
- sequenced PCM input/output framing and ordering rejection;
- backend byte-buffer limits and short-audio rejection;
- explicit development provider selection and unavailable live-provider rejection;
- deterministic mock partial/final events, binary fixture output and metrics;
- Local DSP profile validation, duration changes, amplitude ceiling, fades and real transformed binary output;
- TypeScript type-check, production build, Python lint and tests.

## Operational now

- `scripts/smoke_test.ps1` checks a running application's health and catalogue;
- the smoke test exercises Mock contract and Local DSP with synthetic sequenced PCM, validates events, binary ordering and changed DSP output, then restores Replay;
- `scripts/burn_in.ps1` performs repeated create/reset cycles;
- manually verify microphone permission denial and approval, device selection, live level, hold/release capture, eight-second auto-stop, original playback, mute, clear, reset, browser refresh and unplug/replug;
- manually verify both transformation modes, all 18 replay WAV files, cancel, reset and staff panel at the event resolution;
- perform a 60-minute replay loop and inspect memory before promotion.

## Required for later live milestones

Test silence detection, explicit output-device selection, gateway restart/disconnect, binary frame order and backpressure, cancellation latency, model memory release, 50-session live reset, 60-minute live burn-in and whole-stack GPU/port coexistence.
