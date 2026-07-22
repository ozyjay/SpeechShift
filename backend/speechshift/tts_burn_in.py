from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel, Field

from speechshift.tts_probe import (
    HardwareMonitor,
    HardwareSample,
    ThermalLimits,
    TtsProbeOutcome,
    TtsProbeResult,
    run_isolated_tts_probe,
)

VRAM_RECOVERY_TOLERANCE_MB = 64.0
CANCELLATION_DEADLINE_MS = 250


class BurnInMode(StrEnum):
    CANCELLATION = "cancellation"
    TIMEOUT = "timeout"
    COMPLETION = "completion"


class BurnInRun(BaseModel):
    cycle: int = Field(ge=1)
    mode: BurnInMode
    probe: TtsProbeResult
    baseline_vram_mb: float = Field(ge=0)
    recovered_vram_mb: float = Field(ge=0)
    memory_recovery_ms: int = Field(ge=0)
    memory_recovered: bool


class TtsBurnInSummary(BaseModel):
    cycles_requested: int = Field(ge=1)
    cycles_completed: int = Field(ge=0)
    passed: bool
    failures: list[str]
    runs: list[BurnInRun]
    peak_gpu_temperature_c: float
    peak_cpu_temperature_c: float
    maximum_start_gpu_c: float
    maximum_start_cpu_c: float
    cutoff_gpu_c: float
    cutoff_cpu_c: float
    vram_recovery_tolerance_mb: float


def run_tts_burn_in(
    command: list[str],
    hardware_monitor: HardwareMonitor,
    *,
    cycles: int,
    startup_timeout_seconds: float,
    generation_timeout_seconds: float,
    cancel_after_seconds: float,
    forced_timeout_seconds: float,
    memory_recovery_timeout_seconds: float,
    cooldown_timeout_seconds: float,
    thermal_limits: ThermalLimits | None = None,
) -> TtsBurnInSummary:
    if cycles < 1:
        raise ValueError("burn-in cycles must be positive")
    if cancel_after_seconds < 0 or forced_timeout_seconds <= 0:
        raise ValueError("burn-in cancellation and timeout delays are invalid")
    if memory_recovery_timeout_seconds <= 0 or cooldown_timeout_seconds < 0:
        raise ValueError("burn-in recovery and cooldown timeouts are invalid")

    limits = thermal_limits or ThermalLimits()
    runs: list[BurnInRun] = []
    failures: list[str] = []
    observed_samples: list[HardwareSample] = []
    cycles_completed = 0

    for cycle in range(1, cycles + 1):
        cycle_complete = True
        for mode in BurnInMode:
            start_sample = _wait_until_safe_to_start(
                hardware_monitor,
                limits,
                cooldown_timeout_seconds,
                observed_samples,
            )
            if start_sample is None:
                failures.append(f"cycle {cycle} {mode}: hardware did not cool to start limits")
                cycle_complete = False
                break

            result = run_isolated_tts_probe(
                command,
                startup_timeout_seconds=startup_timeout_seconds,
                generation_timeout_seconds=(
                    forced_timeout_seconds
                    if mode is BurnInMode.TIMEOUT
                    else generation_timeout_seconds
                ),
                cancel_after_seconds=(
                    cancel_after_seconds if mode is BurnInMode.CANCELLATION else None
                ),
                environment={"SPEECHSHIFT_PROBE_MODE": mode},
                cancellation_deadline_ms=CANCELLATION_DEADLINE_MS,
                hardware_monitor=hardware_monitor,
                thermal_limits=limits,
            )
            recovered_sample, recovery_ms = _wait_for_memory_recovery(
                hardware_monitor,
                start_sample.vram_used_mb,
                memory_recovery_timeout_seconds,
                limits,
                observed_samples,
            )
            memory_recovered = (
                recovered_sample.vram_used_mb
                <= start_sample.vram_used_mb + VRAM_RECOVERY_TOLERANCE_MB
            )
            run = BurnInRun(
                cycle=cycle,
                mode=mode,
                probe=result,
                baseline_vram_mb=start_sample.vram_used_mb,
                recovered_vram_mb=recovered_sample.vram_used_mb,
                memory_recovery_ms=recovery_ms,
                memory_recovered=memory_recovered,
            )
            runs.append(run)
            observed_samples.append(recovered_sample)
            run_failures = _run_failures(run)
            failures.extend(f"cycle {cycle} {mode}: {failure}" for failure in run_failures)
            if result.outcome is TtsProbeOutcome.THERMAL_CUTOFF:
                cycle_complete = False
                break
        if cycle_complete:
            cycles_completed += 1
        else:
            break

    if not observed_samples:
        observed_samples.append(hardware_monitor.sample())
    probe_gpu_peaks = [
        run.probe.peak_gpu_temperature_c
        for run in runs
        if run.probe.peak_gpu_temperature_c is not None
    ]
    probe_cpu_peaks = [
        run.probe.peak_cpu_temperature_c
        for run in runs
        if run.probe.peak_cpu_temperature_c is not None
    ]
    return TtsBurnInSummary(
        cycles_requested=cycles,
        cycles_completed=cycles_completed,
        passed=not failures and cycles_completed == cycles,
        failures=failures,
        runs=runs,
        peak_gpu_temperature_c=max(
            [sample.gpu_temperature_c for sample in observed_samples] + probe_gpu_peaks
        ),
        peak_cpu_temperature_c=max(
            [sample.cpu_temperature_c for sample in observed_samples] + probe_cpu_peaks
        ),
        maximum_start_gpu_c=limits.maximum_start_gpu_c,
        maximum_start_cpu_c=limits.maximum_start_cpu_c,
        cutoff_gpu_c=limits.cutoff_gpu_c,
        cutoff_cpu_c=limits.cutoff_cpu_c,
        vram_recovery_tolerance_mb=VRAM_RECOVERY_TOLERANCE_MB,
    )


def _wait_until_safe_to_start(
    monitor: HardwareMonitor,
    limits: ThermalLimits,
    timeout_seconds: float,
    observed_samples: list[HardwareSample],
) -> HardwareSample | None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        sample = monitor.sample()
        observed_samples.append(sample)
        if (
            sample.gpu_temperature_c <= limits.maximum_start_gpu_c
            and sample.cpu_temperature_c <= limits.maximum_start_cpu_c
        ):
            return sample
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(remaining, limits.sample_interval_seconds))


def _wait_for_memory_recovery(
    monitor: HardwareMonitor,
    baseline_vram_mb: float,
    timeout_seconds: float,
    limits: ThermalLimits,
    observed_samples: list[HardwareSample],
) -> tuple[HardwareSample, int]:
    started = time.monotonic()
    deadline = started + timeout_seconds
    while True:
        sample = monitor.sample()
        observed_samples.append(sample)
        elapsed_ms = round((time.monotonic() - started) * 1_000)
        if sample.vram_used_mb <= baseline_vram_mb + VRAM_RECOVERY_TOLERANCE_MB:
            return sample, elapsed_ms
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return sample, elapsed_ms
        time.sleep(min(remaining, limits.sample_interval_seconds))


def _run_failures(run: BurnInRun) -> list[str]:
    failures: list[str] = []
    expected = {
        BurnInMode.CANCELLATION: TtsProbeOutcome.CANCELLED,
        BurnInMode.TIMEOUT: TtsProbeOutcome.GENERATION_TIMEOUT,
        BurnInMode.COMPLETION: TtsProbeOutcome.COMPLETED,
    }[run.mode]
    if run.probe.outcome is not expected:
        failures.append(f"expected {expected}, received {run.probe.outcome}")
    if not run.probe.worker_exited:
        failures.append("worker did not exit")
    if run.mode in {BurnInMode.CANCELLATION, BurnInMode.TIMEOUT}:
        latency = run.probe.cancellation_latency_ms
        if latency is None or latency > CANCELLATION_DEADLINE_MS:
            failures.append("worker termination exceeded 250 ms")
    if run.mode is BurnInMode.COMPLETION and run.probe.clipped_sample_percent != 0:
        failures.append("completed output contained clipped samples")
    if not run.memory_recovered:
        failures.append("GPU VRAM did not recover to baseline tolerance")
    return failures
