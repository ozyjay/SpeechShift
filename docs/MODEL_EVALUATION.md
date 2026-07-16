# Model evaluation

No live speech model is selected in this milestone. Selection requires current primary-source research plus physical Fedora 44/ROCm probes on the Framework Desktop.

Candidate groups for the next spikes are maintained voice-conversion systems, Whisper-family speech recognition, a constrained translation model, multilingual TTS such as maintained Qwen or CosyVoice releases, and end-to-end speech translation such as maintained Seamless variants. Every serious candidate must record repository/model identifier, licence, parameters and precision, measured memory and latency, languages, streaming and cancellation, CUDA/Triton assumptions, ROCm evidence, offline behaviour, clean shutdown/memory release and maintenance status.

ROCm support must not be claimed from CUDA compatibility assumptions. A candidate is promoted only after a reproducible local probe against the event fingerprint and public-demo licence review. Until then, `local` and `modeldeck` remain unavailable and replay remains the operational provider.

