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
