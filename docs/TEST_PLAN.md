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
- TypeScript type-check, production build, Python lint and tests.

## Operational now

- `scripts/smoke_test.ps1` checks a running application's health and catalogue;
- `scripts/burn_in.ps1` performs repeated create/reset cycles;
- manually verify both modes, all 18 WAV files, mute, cancel, reset, browser refresh and staff panel at the event resolution;
- perform a 60-minute replay loop and inspect memory before promotion.

## Required for later live milestones

Test microphone permission, input device change, bounded PCM capture, silence detection, unplug/replug, output selection, gateway restart/disconnect, binary frame order and backpressure, cancellation latency, model memory release, 50-session live reset, 60-minute live burn-in and whole-stack GPU/port coexistence.

