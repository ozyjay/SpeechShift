from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

SYNTHETIC_TEXT = "Welcome to JCU Open Day."


def _emit(event: dict[str, object]) -> None:
    print(json.dumps(event), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the pinned Qwen TTS candidate without retaining generated audio."
    )
    parser.add_argument("model", type=Path)
    args = parser.parse_args()

    try:
        if not args.model.is_dir():
            raise ValueError("Qwen model path must be an existing directory")
        with contextlib.redirect_stdout(sys.stderr):
            import torch
            from qwen_tts import Qwen3TTSModel

            load_started = time.perf_counter()
            model = Qwen3TTSModel.from_pretrained(
                str(args.model),
                device_map="cuda:0",
                dtype=torch.bfloat16,
                attn_implementation="sdpa",
                local_files_only=True,
            )
        load_time_ms = round((time.perf_counter() - load_started) * 1_000)
        _emit({"event": "ready", "load_time_ms": load_time_ms})

        torch.cuda.reset_peak_memory_stats()
        generation_started = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr), torch.inference_mode():
            waveforms, sample_rate = model.generate_custom_voice(
                text=SYNTHETIC_TEXT,
                language="English",
                speaker="Ryan",
                do_sample=True,
                subtalker_dosample=True,
                max_new_tokens=256,
            )
        generation_time_ms = round((time.perf_counter() - generation_started) * 1_000)
        waveform = waveforms[0]
        audio_duration_ms = round(len(waveform) / sample_rate * 1_000)
        clipped_sample_percent = float(
            ((waveform <= -1.0) | (waveform >= 1.0)).sum() / len(waveform) * 100
        )
        _emit(
            {
                "event": "result",
                "generation_time_ms": generation_time_ms,
                "audio_duration_ms": audio_duration_ms,
                "peak_vram_mb": round(torch.cuda.max_memory_allocated() / 1024**2),
                "clipped_sample_percent": clipped_sample_percent,
            }
        )
        return 0
    except Exception as error:
        _emit({"event": "error", "error_type": type(error).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
