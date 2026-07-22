from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

WORKER_SHUTDOWN_TIMEOUT_SECONDS = 5.0


class TtsProbeOutcome(StrEnum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STARTUP_TIMEOUT = "startup-timeout"
    GENERATION_TIMEOUT = "generation-timeout"
    THERMAL_CUTOFF = "thermal-cutoff"
    WORKER_ERROR = "worker-error"


class TtsProbeResult(BaseModel):
    outcome: TtsProbeOutcome
    load_time_ms: int | None = Field(default=None, ge=0)
    generation_time_ms: int | None = Field(default=None, ge=0)
    audio_duration_ms: int | None = Field(default=None, ge=0)
    peak_vram_mb: int | None = Field(default=None, ge=0)
    clipped_sample_percent: float | None = Field(default=None, ge=0, le=100)
    cancellation_latency_ms: int | None = Field(default=None, ge=0)
    worker_exit_code: int | None
    worker_exited: bool
    error_type: str | None = None
    peak_gpu_temperature_c: float | None = None
    peak_cpu_temperature_c: float | None = None
    thermal_cutoff_sensor: str | None = None


class ThermalLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    maximum_start_gpu_c: float = 55.0
    maximum_start_cpu_c: float = 75.0
    cutoff_gpu_c: float = 80.0
    cutoff_cpu_c: float = 95.0
    sample_interval_seconds: float = Field(default=0.25, gt=0, le=1)


class HardwareSample(BaseModel):
    gpu_temperature_c: float
    cpu_temperature_c: float
    vram_used_mb: float = Field(ge=0)


class HardwareMonitor(Protocol):
    def sample(self) -> HardwareSample:
        """Read current temperatures and total GPU VRAM usage."""


@dataclass(frozen=True, slots=True)
class SysfsHardwareMonitor:
    gpu_temperature_path: Path
    cpu_temperature_path: Path
    vram_used_path: Path

    @classmethod
    def discover(cls, root: Path = Path("/sys")) -> SysfsHardwareMonitor:
        hwmon_root = root / "class" / "hwmon"
        gpu_temperature_path = _find_temperature_sensor(hwmon_root, "amdgpu", "edge")
        cpu_temperature_path = _find_temperature_sensor(hwmon_root, "k10temp", "Tctl")
        vram_paths = sorted((root / "class" / "drm").glob("card*/device/mem_info_vram_used"))
        if len(vram_paths) != 1:
            raise RuntimeError("exactly one GPU VRAM usage sensor is required")
        return cls(gpu_temperature_path, cpu_temperature_path, vram_paths[0])

    def sample(self) -> HardwareSample:
        return HardwareSample(
            gpu_temperature_c=_read_number(self.gpu_temperature_path) / 1_000,
            cpu_temperature_c=_read_number(self.cpu_temperature_path) / 1_000,
            vram_used_mb=_read_number(self.vram_used_path) / 1024**2,
        )


@dataclass(slots=True)
class _ThermalState:
    peak_gpu_c: float | None = None
    peak_cpu_c: float | None = None

    def observe(self, sample: HardwareSample) -> None:
        self.peak_gpu_c = max(self.peak_gpu_c or sample.gpu_temperature_c, sample.gpu_temperature_c)
        self.peak_cpu_c = max(self.peak_cpu_c or sample.cpu_temperature_c, sample.cpu_temperature_c)


class _ThermalCutoff(RuntimeError):
    def __init__(self, sensor: str) -> None:
        self.sensor = sensor


class WorkerProtocolError(RuntimeError):
    pass


class _WorkerEventReader:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        if process.stdout is None:
            raise RuntimeError("worker stdout is unavailable")
        self._descriptor = process.stdout.fileno()
        self._buffer = bytearray()

    def read(self, timeout_seconds: float) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        while b"\n" not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            with selectors.DefaultSelector() as selector:
                selector.register(self._descriptor, selectors.EVENT_READ)
                if not selector.select(remaining):
                    raise TimeoutError
            chunk = os.read(self._descriptor, 4_096)
            if not chunk:
                raise EOFError
            self._buffer.extend(chunk)
        line, _, remainder = self._buffer.partition(b"\n")
        self._buffer = bytearray(remainder)
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WorkerProtocolError("worker emitted invalid JSON") from error
        if not isinstance(event, dict):
            raise WorkerProtocolError("worker event must be a JSON object")
        return event


def run_isolated_tts_probe(
    command: list[str],
    *,
    startup_timeout_seconds: float,
    generation_timeout_seconds: float,
    cancel_after_seconds: float | None = None,
    environment: dict[str, str] | None = None,
    cancellation_deadline_ms: int = 250,
    hardware_monitor: HardwareMonitor | None = None,
    thermal_limits: ThermalLimits | None = None,
) -> TtsProbeResult:
    if not command:
        raise ValueError("worker command must not be empty")
    if startup_timeout_seconds <= 0 or generation_timeout_seconds <= 0:
        raise ValueError("probe timeouts must be positive")
    if cancel_after_seconds is not None and cancel_after_seconds < 0:
        raise ValueError("cancel delay must not be negative")
    limits = thermal_limits or ThermalLimits()
    thermal_state = _ThermalState()
    if hardware_monitor is not None:
        initial = hardware_monitor.sample()
        thermal_state.observe(initial)
        unsafe_sensor = _unsafe_start_sensor(initial, limits)
        if unsafe_sensor:
            return _thermal_result(None, thermal_state, f"{unsafe_sensor}-start")

    worker_environment = os.environ.copy()
    worker_environment.update(
        {
            "HF_DATASETS_OFFLINE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    if environment:
        worker_environment.update(environment)

    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=worker_environment,
        start_new_session=True,
    )
    reader = _WorkerEventReader(process)
    try:
        ready = _read_event_with_monitor(
            reader,
            startup_timeout_seconds,
            hardware_monitor,
            limits,
            thermal_state,
        )
    except _ThermalCutoff as error:
        _terminate_worker_group(process, cancellation_deadline_ms)
        return _thermal_result(process, thermal_state, error.sensor)
    except TimeoutError:
        cancellation_latency_ms = _terminate_worker_group(process, cancellation_deadline_ms)
        return _stopped_result(
            TtsProbeOutcome.STARTUP_TIMEOUT,
            process,
            cancellation_latency_ms,
            thermal_state=thermal_state,
        )
    except (EOFError, WorkerProtocolError):
        process.wait()
        return _worker_error_result(process)

    if ready.get("event") == "error":
        process.wait()
        return _worker_error_result(process, ready)
    if ready.get("event") != "ready" or not isinstance(ready.get("load_time_ms"), int):
        _terminate_worker_group(process, cancellation_deadline_ms)
        raise WorkerProtocolError("worker did not emit a valid ready event")
    load_time_ms = ready["load_time_ms"]

    if cancel_after_seconds is not None:
        try:
            _wait_for_process_with_monitor(
                process,
                cancel_after_seconds,
                hardware_monitor,
                limits,
                thermal_state,
            )
        except _ThermalCutoff as error:
            _terminate_worker_group(process, cancellation_deadline_ms)
            return _thermal_result(process, thermal_state, error.sensor)
        if process.poll() is None:
            cancellation_latency_ms = _terminate_worker_group(process, cancellation_deadline_ms)
            return _stopped_result(
                TtsProbeOutcome.CANCELLED,
                process,
                cancellation_latency_ms,
                load_time_ms=load_time_ms,
                thermal_state=thermal_state,
            )
        return _result_after_exit(process, reader, load_time_ms, thermal_state)

    try:
        result_event = _read_event_with_monitor(
            reader,
            generation_timeout_seconds,
            hardware_monitor,
            limits,
            thermal_state,
        )
    except _ThermalCutoff as error:
        _terminate_worker_group(process, cancellation_deadline_ms)
        return _thermal_result(process, thermal_state, error.sensor)
    except TimeoutError:
        cancellation_latency_ms = _terminate_worker_group(process, cancellation_deadline_ms)
        return _stopped_result(
            TtsProbeOutcome.GENERATION_TIMEOUT,
            process,
            cancellation_latency_ms,
            load_time_ms=load_time_ms,
            thermal_state=thermal_state,
        )
    except (EOFError, WorkerProtocolError):
        process.wait()
        return _worker_error_result(process, load_time_ms=load_time_ms)

    try:
        _wait_for_process_with_monitor(
            process,
            WORKER_SHUTDOWN_TIMEOUT_SECONDS,
            hardware_monitor,
            limits,
            thermal_state,
        )
    except _ThermalCutoff as error:
        _terminate_worker_group(process, cancellation_deadline_ms)
        return _thermal_result(process, thermal_state, error.sensor)
    if process.poll() is None:
        _terminate_worker_group(process, cancellation_deadline_ms)
        return _worker_error_result(
            process,
            {"error_type": "ShutdownTimeout"},
            load_time_ms,
            thermal_state,
        )
    if result_event.get("event") == "error":
        return _worker_error_result(process, result_event, load_time_ms, thermal_state)
    if result_event.get("event") != "result":
        raise WorkerProtocolError("worker did not emit a result event")
    return TtsProbeResult(
        outcome=TtsProbeOutcome.COMPLETED,
        load_time_ms=load_time_ms,
        generation_time_ms=_required_non_negative_int(result_event, "generation_time_ms"),
        audio_duration_ms=_required_non_negative_int(result_event, "audio_duration_ms"),
        peak_vram_mb=_required_non_negative_int(result_event, "peak_vram_mb"),
        clipped_sample_percent=_required_percentage(result_event, "clipped_sample_percent"),
        worker_exit_code=process.returncode,
        worker_exited=process.poll() is not None,
        **_thermal_fields(thermal_state),
    )


def _read_event_with_monitor(
    reader: _WorkerEventReader,
    timeout_seconds: float,
    monitor: HardwareMonitor | None,
    limits: ThermalLimits,
    state: _ThermalState,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        _sample_and_enforce(monitor, limits, state)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        try:
            return reader.read(min(remaining, limits.sample_interval_seconds))
        except TimeoutError:
            continue


def _wait_for_process_with_monitor(
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
    monitor: HardwareMonitor | None,
    limits: ThermalLimits,
    state: _ThermalState,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None:
        _sample_and_enforce(monitor, limits, state)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, limits.sample_interval_seconds))


def _sample_and_enforce(
    monitor: HardwareMonitor | None, limits: ThermalLimits, state: _ThermalState
) -> None:
    if monitor is None:
        return
    sample = monitor.sample()
    state.observe(sample)
    if sample.gpu_temperature_c >= limits.cutoff_gpu_c:
        raise _ThermalCutoff("gpu")
    if sample.cpu_temperature_c >= limits.cutoff_cpu_c:
        raise _ThermalCutoff("cpu")


def _terminate_worker_group(process: subprocess.Popen[bytes], deadline_ms: int) -> int:
    if process.poll() is not None:
        return 0
    started = time.perf_counter()
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=deadline_ms / 1_000)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    return round((time.perf_counter() - started) * 1_000)


def _result_after_exit(
    process: subprocess.Popen[bytes],
    reader: _WorkerEventReader,
    load_time_ms: int,
    thermal_state: _ThermalState,
) -> TtsProbeResult:
    try:
        event = reader.read(0.1)
    except (EOFError, TimeoutError, WorkerProtocolError):
        return _worker_error_result(process, load_time_ms=load_time_ms)
    if event.get("event") == "error":
        return _worker_error_result(process, event, load_time_ms)
    if event.get("event") != "result":
        return _worker_error_result(process, load_time_ms=load_time_ms)
    return TtsProbeResult(
        outcome=TtsProbeOutcome.COMPLETED,
        load_time_ms=load_time_ms,
        generation_time_ms=_required_non_negative_int(event, "generation_time_ms"),
        audio_duration_ms=_required_non_negative_int(event, "audio_duration_ms"),
        peak_vram_mb=_required_non_negative_int(event, "peak_vram_mb"),
        clipped_sample_percent=_required_percentage(event, "clipped_sample_percent"),
        worker_exit_code=process.returncode,
        worker_exited=True,
        **_thermal_fields(thermal_state),
    )


def _stopped_result(
    outcome: TtsProbeOutcome,
    process: subprocess.Popen[bytes],
    cancellation_latency_ms: int,
    *,
    load_time_ms: int | None = None,
    thermal_state: _ThermalState | None = None,
) -> TtsProbeResult:
    return TtsProbeResult(
        outcome=outcome,
        load_time_ms=load_time_ms,
        cancellation_latency_ms=cancellation_latency_ms,
        worker_exit_code=process.returncode,
        worker_exited=process.poll() is not None,
        **_thermal_fields(thermal_state),
    )


def _thermal_result(
    process: subprocess.Popen[bytes] | None,
    thermal_state: _ThermalState,
    sensor: str,
) -> TtsProbeResult:
    return TtsProbeResult(
        outcome=TtsProbeOutcome.THERMAL_CUTOFF,
        worker_exit_code=process.returncode if process is not None else None,
        worker_exited=process is None or process.poll() is not None,
        thermal_cutoff_sensor=sensor,
        **_thermal_fields(thermal_state),
    )


def _worker_error_result(
    process: subprocess.Popen[bytes],
    event: dict[str, object] | None = None,
    load_time_ms: int | None = None,
    thermal_state: _ThermalState | None = None,
) -> TtsProbeResult:
    error_type = event.get("error_type") if event else None
    return TtsProbeResult(
        outcome=TtsProbeOutcome.WORKER_ERROR,
        load_time_ms=load_time_ms,
        worker_exit_code=process.returncode,
        worker_exited=process.poll() is not None,
        error_type=error_type if isinstance(error_type, str) else None,
        **_thermal_fields(thermal_state),
    )


def _required_non_negative_int(event: dict[str, object], key: str) -> int:
    value = event.get(key)
    if not isinstance(value, int) or value < 0:
        raise WorkerProtocolError(f"worker result has invalid {key}")
    return value


def _required_percentage(event: dict[str, object], key: str) -> float:
    value = event.get(key)
    if not isinstance(value, int | float) or not 0 <= value <= 100:
        raise WorkerProtocolError(f"worker result has invalid {key}")
    return float(value)


def _thermal_fields(state: _ThermalState | None) -> dict[str, float | None]:
    return {
        "peak_gpu_temperature_c": state.peak_gpu_c if state else None,
        "peak_cpu_temperature_c": state.peak_cpu_c if state else None,
    }


def _unsafe_start_sensor(sample: HardwareSample, limits: ThermalLimits) -> str | None:
    if sample.gpu_temperature_c > limits.maximum_start_gpu_c:
        return "gpu"
    if sample.cpu_temperature_c > limits.maximum_start_cpu_c:
        return "cpu"
    return None


def _find_temperature_sensor(hwmon_root: Path, device: str, label: str) -> Path:
    for directory in sorted(hwmon_root.glob("hwmon*")):
        try:
            if (directory / "name").read_text(encoding="utf-8").strip() != device:
                continue
            for label_path in sorted(directory.glob("temp*_label")):
                if label_path.read_text(encoding="utf-8").strip() == label:
                    return label_path.with_name(label_path.name.replace("_label", "_input"))
        except OSError:
            continue
    raise RuntimeError(f"cannot find {device} {label} temperature sensor")


def _read_number(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as error:
        raise RuntimeError(f"cannot read hardware sensor {path.name}") from error
