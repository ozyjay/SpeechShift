import json
import sys
from pathlib import Path

import speechshift.tts_probe as tts_probe
from speechshift.tts_burn_in import BurnInMode, run_tts_burn_in
from speechshift.tts_probe import (
    HardwareSample,
    SysfsHardwareMonitor,
    ThermalLimits,
    TtsProbeOutcome,
    run_isolated_tts_probe,
)


def worker(script: str) -> list[str]:
    return [sys.executable, "-u", "-c", script]


class ConstantHardwareMonitor:
    def __init__(self, gpu_c: float = 40, cpu_c: float = 50, vram_mb: float = 100) -> None:
        self.current = HardwareSample(
            gpu_temperature_c=gpu_c,
            cpu_temperature_c=cpu_c,
            vram_used_mb=vram_mb,
        )

    def sample(self) -> HardwareSample:
        return self.current


class SequenceHardwareMonitor:
    def __init__(self, samples: list[HardwareSample]) -> None:
        self.samples = iter(samples)
        self.last = samples[-1]

    def sample(self) -> HardwareSample:
        self.last = next(self.samples, self.last)
        return self.last


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


def test_probe_terminates_worker_that_hangs_during_shutdown(monkeypatch) -> None:
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
    monkeypatch.setattr(tts_probe, "WORKER_SHUTDOWN_TIMEOUT_SECONDS", 0.01)
    probe = run_isolated_tts_probe(
        worker(
            f"import time; print({ready!r}, flush=True); print({result!r}, flush=True); "
            "time.sleep(60)"
        ),
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
    )
    assert probe.outcome is TtsProbeOutcome.WORKER_ERROR
    assert probe.error_type == "ShutdownTimeout"
    assert probe.worker_exited is True


def test_probe_refuses_to_start_above_safe_temperature() -> None:
    probe = run_isolated_tts_probe(
        worker("raise RuntimeError('must not start')"),
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
        hardware_monitor=ConstantHardwareMonitor(gpu_c=56),
    )
    assert probe.outcome is TtsProbeOutcome.THERMAL_CUTOFF
    assert probe.thermal_cutoff_sensor == "gpu-start"
    assert probe.worker_exit_code is None
    assert probe.worker_exited is True


def test_probe_refuses_to_start_above_safe_cpu_temperature() -> None:
    probe = run_isolated_tts_probe(
        worker("raise RuntimeError('must not start')"),
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
        hardware_monitor=ConstantHardwareMonitor(cpu_c=76),
    )
    assert probe.outcome is TtsProbeOutcome.THERMAL_CUTOFF
    assert probe.thermal_cutoff_sensor == "cpu-start"
    assert probe.worker_exit_code is None


def test_probe_terminates_worker_at_active_thermal_cutoff() -> None:
    monitor = SequenceHardwareMonitor(
        [
            HardwareSample(gpu_temperature_c=40, cpu_temperature_c=50, vram_used_mb=100),
            HardwareSample(gpu_temperature_c=80, cpu_temperature_c=50, vram_used_mb=100),
        ]
    )
    probe = run_isolated_tts_probe(
        worker("import time; time.sleep(60)"),
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
        hardware_monitor=monitor,
        thermal_limits=ThermalLimits(sample_interval_seconds=0.01),
    )
    assert probe.outcome is TtsProbeOutcome.THERMAL_CUTOFF
    assert probe.thermal_cutoff_sensor == "gpu"
    assert probe.peak_gpu_temperature_c == 80
    assert probe.worker_exited is True


def test_sysfs_monitor_discovers_required_sensors(tmp_path: Path) -> None:
    gpu_hwmon = tmp_path / "class/hwmon/hwmon0"
    cpu_hwmon = tmp_path / "class/hwmon/hwmon1"
    drm = tmp_path / "class/drm/card1/device"
    gpu_hwmon.mkdir(parents=True)
    cpu_hwmon.mkdir(parents=True)
    drm.mkdir(parents=True)
    (gpu_hwmon / "name").write_text("amdgpu\n", encoding="utf-8")
    (gpu_hwmon / "temp1_label").write_text("edge\n", encoding="utf-8")
    (gpu_hwmon / "temp1_input").write_text("42000\n", encoding="utf-8")
    (cpu_hwmon / "name").write_text("k10temp\n", encoding="utf-8")
    (cpu_hwmon / "temp1_label").write_text("Tctl\n", encoding="utf-8")
    (cpu_hwmon / "temp1_input").write_text("53000\n", encoding="utf-8")
    (drm / "mem_info_vram_used").write_text(str(128 * 1024**2), encoding="utf-8")

    sample = SysfsHardwareMonitor.discover(tmp_path).sample()
    assert sample.gpu_temperature_c == 42
    assert sample.cpu_temperature_c == 53
    assert sample.vram_used_mb == 128


def test_burn_in_exercises_cancellation_timeout_and_completion() -> None:
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
    script = (
        "import os,time; "
        f"print({ready!r}, flush=True); "
        f"print({result!r}, flush=True) "
        "if os.environ['SPEECHSHIFT_PROBE_MODE'] == 'completion' else time.sleep(60)"
    )
    summary = run_tts_burn_in(
        worker(script),
        ConstantHardwareMonitor(),
        cycles=1,
        startup_timeout_seconds=1,
        generation_timeout_seconds=1,
        cancel_after_seconds=0.01,
        forced_timeout_seconds=0.01,
        memory_recovery_timeout_seconds=0.1,
        cooldown_timeout_seconds=0.1,
        thermal_limits=ThermalLimits(sample_interval_seconds=0.005),
    )
    assert summary.passed is True
    assert summary.cycles_completed == 1
    assert [run.mode for run in summary.runs] == [
        BurnInMode.CANCELLATION,
        BurnInMode.TIMEOUT,
        BurnInMode.COMPLETION,
    ]
    assert all(run.memory_recovered for run in summary.runs)
