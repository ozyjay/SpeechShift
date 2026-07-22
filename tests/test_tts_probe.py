import json
import sys

from speechshift.tts_probe import TtsProbeOutcome, run_isolated_tts_probe


def worker(script: str) -> list[str]:
    return [sys.executable, "-u", "-c", script]


def test_isolated_probe_returns_completed_metrics() -> None:
    ready = json.dumps({"event": "ready", "load_time_ms": 12})
    result = json.dumps(
        {
            "event": "result",
            "generation_time_ms": 34,
            "audio_duration_ms": 56,
            "peak_vram_mb": 78,
            "clipped_sample_percent": 0,
        }
    )
    probe = run_isolated_tts_probe(
        worker(f"print({ready!r}, flush=True); print({result!r}, flush=True)"),
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
    )
    assert probe.outcome is TtsProbeOutcome.COMPLETED
    assert probe.load_time_ms == 12
    assert probe.generation_time_ms == 34
    assert probe.audio_duration_ms == 56
    assert probe.peak_vram_mb == 78
    assert probe.clipped_sample_percent == 0
    assert probe.worker_exit_code == 0
    assert probe.worker_exited is True


def test_isolated_probe_cancels_generation_after_ready() -> None:
    ready = json.dumps({"event": "ready", "load_time_ms": 12})
    probe = run_isolated_tts_probe(
        worker(f"import time; print({ready!r}, flush=True); time.sleep(60)"),
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
        cancel_after_seconds=0.01,
    )
    assert probe.outcome is TtsProbeOutcome.CANCELLED
    assert probe.load_time_ms == 12
    assert probe.cancellation_latency_ms is not None
    assert probe.cancellation_latency_ms <= 250
    assert probe.worker_exited is True


def test_isolated_probe_enforces_startup_timeout() -> None:
    probe = run_isolated_tts_probe(
        worker("import time; time.sleep(60)"),
        startup_timeout_seconds=0.01,
        generation_timeout_seconds=1,
    )
    assert probe.outcome is TtsProbeOutcome.STARTUP_TIMEOUT
    assert probe.worker_exited is True


def test_isolated_probe_enforces_generation_timeout() -> None:
    ready = json.dumps({"event": "ready", "load_time_ms": 12})
    probe = run_isolated_tts_probe(
        worker(f"import time; print({ready!r}, flush=True); time.sleep(60)"),
        startup_timeout_seconds=1,
        generation_timeout_seconds=0.01,
    )
    assert probe.outcome is TtsProbeOutcome.GENERATION_TIMEOUT
    assert probe.load_time_ms == 12
    assert probe.worker_exited is True


def test_isolated_probe_reports_sanitised_worker_error() -> None:
    event = json.dumps({"event": "error", "error_type": "RuntimeError"})
    probe = run_isolated_tts_probe(
        worker(f"import sys; print({event!r}, flush=True); sys.exit(1)"),
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
    )
    assert probe.outcome is TtsProbeOutcome.WORKER_ERROR
    assert probe.error_type == "RuntimeError"
    assert probe.worker_exit_code == 1
    assert probe.worker_exited is True
