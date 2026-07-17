# Model evaluation

No live speech model is selected in this milestone. Selection requires current primary-source research plus physical Fedora 44/ROCm probes on the Framework Desktop.

Candidate groups for the next spikes are maintained voice-conversion systems, Whisper-family speech recognition, a constrained translation model, multilingual TTS such as maintained Qwen or CosyVoice releases, and end-to-end speech translation such as maintained Seamless variants. Every serious candidate must record repository/model identifier, licence, parameters and precision, measured memory and latency, languages, streaming and cancellation, CUDA/Triton assumptions, ROCm evidence, offline behaviour, clean shutdown/memory release and maintenance status.

ROCm support must not be claimed from CUDA compatibility assumptions. A candidate is promoted only after a reproducible local probe against the event fingerprint and public-demo licence review. Local DSP is available only as a non-model development baseline; model-backed `local` and `modeldeck` capabilities remain unavailable and replay remains the operational provider.

## Reproducible readiness record

Copy `docs/model_candidate.example.json`, replace every placeholder with primary-source candidate facts and pin an exact revision. Prepare a record on the event machine:

```powershell
.venv/bin/python scripts/model_probe.py prepare docs/my-candidate.json probe-result.json
```

The command records the Fedora, kernel, Python, repository revision and available ROCm facts. It deliberately does not infer compatibility from installed tools. Run the candidate offline, complete every measurement and boolean check in the generated record, then evaluate it. Latency and memory acceptance must reflect the event journey and whole-stack GPU budget, not an isolated successful inference:

```powershell
.venv/bin/python scripts/model_probe.py evaluate probe-result.json
```

A prepared or partially completed record fails closed. Probe results are local engineering artefacts and should not contain visitor audio, transcripts, credentials or private system data.

## First physical probe: Whisper `small.en`

The first Framework Desktop probe used the pinned candidate in `docs/model_candidates/whisper-small-en-rocm.json`. OpenAI Whisper `small.en` completed FP16 inference on the Radeon 8060S (`gfx1151`) through PyTorch's ROCm 7.1 build. A synthetic 4.85-second Australian English sample produced an exact normalised match in 1.01 seconds after a 1.49-second cached model load. Peak tracked GPU allocation was 1,294 MB and peak process RSS was 2,272 MB.

Fedora's installed HSA runtime must currently be preloaded for this path. PyTorch 2.10.0's bundled HSA runtime enumerates the GPU but segfaults on the first tensor operation; the Fedora ROCm 7.1.1 runtime completes the same operation. This is an explicit development-only compatibility requirement, not a silent fallback or an architecture override.

This candidate is **not ready for promotion**. The upstream interface is batch-oriented, the streaming and request-level cancellation gates have not passed, the generic Triton dependency alongside `triton-rocm` needs resolution, and public-output safety review needs a broader corpus. No `local` or `modeldeck` capability is enabled by this probe.

## VoicePrivacy 2026 B3 licence gate

The next direct voice-transformation candidate is pinned in `docs/model_candidates/voiceprivacy-2026-b3-sttts-rocm.json`. VoicePrivacy B3 is relevant because it reconstructs the source phonetic content with modified prosody and a GAN-generated artificial speaker embedding; it does not require a target recording or represent the output as a known person.

The physical model probe is **blocked before download**. VoicePrivacy 2026 and the DigitalPhonetics speaker-anonymization source repositories declare GPL-3.0, but the B3 v2.0 release page does not state a licence for `anonymization.zip`, `asr.zip` or `tts.zip` and provides no model card covering those checkpoint archives. Repository licensing must not be assumed to grant public-demonstration rights for separately distributed model weights.

Run the machine-readable gate with:

```powershell
.venv/bin/python scripts/model_probe.py audit docs/model_candidates/voiceprivacy-2026-b3-sttts-rocm.json
```

Until every archive has an explicit reviewed licence, SpeechShift will not download the checkpoints, construct the isolated model environment, or claim ROCm compatibility. The in-memory probe harness and synthetic twelve-clip eSpeak corpus are implemented and unit tested so physical work can resume without changing the privacy boundary if the rights are clarified. No provider or interface behaviour changes as a result of this blocked candidate.
