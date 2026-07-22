from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from enum import StrEnum

from pydantic import BaseModel, Field


class TtsProbeOutcome(StrEnum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STARTUP_TIMEOUT = "startup-timeout"
    GENERATION_TIMEOUT = "generation-timeout"
    WORKER_ERROR = "worker-error"


class TtsProbeResult(BaseModel):
    outcome: TtsProbeOutcome
    load_time_ms: int | None = Field(default=None, ge=0)
    generation_time_ms: int | None = Field(default=None, ge=0)
    audio_duration_ms: int | None = Field(default=None, ge=0)
    peak_vram_mb: int | None = Field(default=None, ge=0)
    clipped_sample_percent: float | None = Field(default=None, ge=0, le=100)
    cancellation_latency_ms: int | None = Field(default=None, ge=0)
    worker_exit_code: int
    worker_exited: bool
    error_type: str | None = None


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
) -> TtsProbeResult:
    if not command:
        raise ValueError("worker command must not be empty")
    if startup_timeout_seconds <= 0 or generation_timeout_seconds <= 0:
        raise ValueError("probe timeouts must be positive")
    if cancel_after_seconds is not None and cancel_after_seconds < 0:
        raise ValueError("cancel delay must not be negative")

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
        ready = reader.read(startup_timeout_seconds)
    except TimeoutError:
        cancellation_latency_ms = _terminate_worker_group(process, cancellation_deadline_ms)
        return _stopped_result(
            TtsProbeOutcome.STARTUP_TIMEOUT, process, cancellation_latency_ms
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
            process.wait(timeout=cancel_after_seconds)
        except subprocess.TimeoutExpired:
            cancellation_latency_ms = _terminate_worker_group(process, cancellation_deadline_ms)
            return _stopped_result(
                TtsProbeOutcome.CANCELLED,
                process,
                cancellation_latency_ms,
                load_time_ms=load_time_ms,
            )
        return _result_after_exit(process, reader, load_time_ms)

    try:
        result_event = reader.read(generation_timeout_seconds)
    except TimeoutError:
        cancellation_latency_ms = _terminate_worker_group(process, cancellation_deadline_ms)
        return _stopped_result(
            TtsProbeOutcome.GENERATION_TIMEOUT,
            process,
            cancellation_latency_ms,
            load_time_ms=load_time_ms,
        )
    except (EOFError, WorkerProtocolError):
        process.wait()
        return _worker_error_result(process, load_time_ms=load_time_ms)

    process.wait()
    if result_event.get("event") == "error":
        return _worker_error_result(process, result_event, load_time_ms)
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
    )


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
    process: subprocess.Popen[bytes], reader: _WorkerEventReader, load_time_ms: int
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
    )


def _stopped_result(
    outcome: TtsProbeOutcome,
    process: subprocess.Popen[bytes],
    cancellation_latency_ms: int,
    *,
    load_time_ms: int | None = None,
) -> TtsProbeResult:
    return TtsProbeResult(
        outcome=outcome,
        load_time_ms=load_time_ms,
        cancellation_latency_ms=cancellation_latency_ms,
        worker_exit_code=process.returncode,
        worker_exited=process.poll() is not None,
    )


def _worker_error_result(
    process: subprocess.Popen[bytes],
    event: dict[str, object] | None = None,
    load_time_ms: int | None = None,
) -> TtsProbeResult:
    error_type = event.get("error_type") if event else None
    return TtsProbeResult(
        outcome=TtsProbeOutcome.WORKER_ERROR,
        load_time_ms=load_time_ms,
        worker_exit_code=process.returncode,
        worker_exited=process.poll() is not None,
        error_type=error_type if isinstance(error_type, str) else None,
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
