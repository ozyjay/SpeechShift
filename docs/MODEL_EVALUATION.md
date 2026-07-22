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

## Cascaded STT, translation and TTS probe

A practical local cascade was probed on the event machine using pinned Whisper `small.en`, OPUS-MT English-to-French and English-to-German, and Qwen3-TTS 12 Hz 0.6B CustomVoice candidates. The candidate manifests are in `docs/model_candidates/`. All inference used cached files with Hugging Face and Transformers offline modes enabled; no model was downloaded while the application was running. Only the fixed synthetic sentence “Welcome to JCU Open Day. Speech Shift is running locally.” and model-generated audio were used. The verified Qwen and filtered OPUS PyTorch snapshots now reside in the shared Hugging Face cache at `/mnt/work/models/huggingface/hub`, are registered in HuggingFacePull's library metadata and are discoverable by ModelDeck at their pinned revisions. ModelDeck currently inventories them as installed but unsupported until allowlisted Qwen TTS and Marian translation workers are implemented. Whisper's standalone `.pt` checkpoint remains application-local because neither shared-cache manager currently supports that artefact format.

Whisper retained its earlier ROCm result: 1.15 seconds to recognise the Qwen-generated English output, with an exact normalised match. The FP32 OPUS models ran on CPU. English-to-French loaded in 224 ms and translated in 204 ms; English-to-German loaded in 188 ms and translated in 136 ms. The fixed-sentence translations were manually reviewed as suitable for this narrow probe, but this is not a broad translation-quality evaluation.

Qwen3-TTS loaded and generated valid 24 kHz audio on the Radeon 8060S using BF16 and eager PyTorch attention, without FlashAttention, architecture overrides or CPU fallback. The first process generated 7.36 seconds of audio in 72.87 seconds. A second process loaded in 1.47 seconds, then took 46.64 and 50.91 seconds for two consecutive generations producing 4.88 and 5.44 seconds of audio. Warm throughput therefore remained about 9.5 times slower than real time. Peak tracked GPU allocation was 2,445 MB, and none of the three files contained clipped samples. Whisper recognised the first output exactly.

A controlled optimisation pass compared eager attention, standard PyTorch SDPA, deterministic SDPA and PyTorch's experimental ROCm AOTriton SDPA using the same fixed short phrase. Standard SDPA reduced elapsed generation from 36.84 to 25.22 seconds; because sampled clip lengths differed, the normalised throughput improvement was more modest, from 10.01 to 9.55 times slower than real time. Deterministic decoding improved throughput to 9.14 times slower than real time but produced a much longer clip and therefore increased wall time. Experimental AOTriton reached 9.19 times slower than real time, which did not justify its additional runtime risk. All outputs had exact Whisper matches and no clipped samples. The accepted configuration is therefore BF16 with standard PyTorch SDPA, sampling enabled, a resident model and a bounded generation-token limit.

Every optimisation run started below 55 °C GPU edge and 75 °C CPU package temperature. A watchdog sampled both sensors four times per second and would terminate a run at 80 °C GPU or 95 °C CPU. The highest observed values were 67 °C GPU and 71.75 °C CPU, and the machine was allowed to cool between variants.

This TTS candidate is suitable for an explicitly asynchronous development pipeline, where the interface shows staged progress and does not claim real-time output. It is **not ready for provider promotion** because request-level cancellation, timeout cleanup and broader public-output review remain incomplete. The packaged API returns the completed waveform rather than incremental output, so first-audio latency remains the full generation time. No `local` or `modeldeck` capability is enabled by this probe, and replay remains the operational provider.

### Isolated TTS cancellation probe

The checked-in probe runner starts Qwen in its own process group, forces Hugging Face and Transformers offline modes, uses only the fixed synthetic probe sentence and discards the generated waveform after calculating safety measurements. The worker reports when model loading is complete so cancellation measures generation rather than start-up. A hard start-up or generation timeout terminates the complete worker process group; worker errors record only the exception type and never model input or output.

Run a normal completion probe with the isolated model environment and cached snapshot:

```powershell
.venv/bin/python scripts/model_probe.py probe-tts `
  docs/model_candidates/qwen3-tts-0.6b-customvoice-rocm.json `
  /path/to/pinned/qwen-snapshot `
  probe-results/qwen-complete.json `
  --python .model-probes/sensible-pipeline/venv/bin/python
```

Run cancellation after generation has been active for two seconds:

```powershell
.venv/bin/python scripts/model_probe.py probe-tts `
  docs/model_candidates/qwen3-tts-0.6b-customvoice-rocm.json `
  /path/to/pinned/qwen-snapshot `
  probe-results/qwen-cancel.json `
  --python .model-probes/sensible-pipeline/venv/bin/python `
  --cancel-after 2
```

The result distinguishes completion, explicit cancellation, start-up timeout, generation timeout and a sanitised worker error. Process exit is necessary evidence for cleanup, but promotion still requires observing GPU memory return to its pre-probe baseline on the event machine and recording that result in a completed readiness record.

The first physical cancellation run with this checked-in runner loaded the model in 1,531 ms, cancelled two seconds after generation began and terminated the worker cleanly with `SIGTERM` in 114 ms. This passes the 250 ms cancellation-latency gate for the fixed synthetic probe. Repeated cancellation, timeout cleanup, GPU-memory baseline recovery and broader public-output review remain required before provider promotion.
