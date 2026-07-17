from __future__ import annotations

import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class CandidateManifest(BaseModel):
    candidate_id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    licence_reviewed: bool = False
    parameters: str = Field(min_length=1)
    precision: str = Field(min_length=1)
    languages: list[str] = Field(min_length=1)
    framework: str = Field(min_length=1)
    cuda_or_triton_requirements: str = Field(min_length=1)
    maintenance_status: str = Field(min_length=1)


class ProbeMeasurements(BaseModel):
    input_duration_ms: int | None = Field(default=None, ge=0)
    load_time_ms: int | None = Field(default=None, ge=0)
    first_audio_latency_ms: int | None = Field(default=None, ge=0)
    total_latency_ms: int | None = Field(default=None, ge=0)
    cancellation_latency_ms: int | None = Field(default=None, ge=0)
    peak_process_rss_mb: int | None = Field(default=None, ge=0)
    peak_vram_mb: int | None = Field(default=None, ge=0)


class ReadinessChecks(BaseModel):
    rocm_probe_passed: bool = False
    offline_run_passed: bool = False
    streaming_passed: bool = False
    cancellation_passed: bool = False
    latency_accepted: bool = False
    memory_fit_passed: bool = False
    memory_released: bool = False
    clean_shutdown_passed: bool = False
    public_output_reviewed: bool = False


class ProbeRecord(BaseModel):
    schema_version: int = 1
    created_at: str
    candidate: CandidateManifest
    system: dict[str, str]
    measurements: ProbeMeasurements = Field(default_factory=ProbeMeasurements)
    checks: ReadinessChecks = Field(default_factory=ReadinessChecks)
    notes: list[str] = Field(default_factory=list)


def prepare_probe_record(candidate: CandidateManifest) -> ProbeRecord:
    return ProbeRecord(
        created_at=datetime.now(UTC).isoformat(),
        candidate=candidate,
        system={
            "platform": platform.platform(),
            "python": platform.python_version(),
            "kernel": platform.release(),
            "rocm_smi": _command_output(
                ["rocm-smi", "--showproductname", "--showdriverversion", "--showmeminfo", "vram"]
            ),
            "rocminfo_agents": _command_output(["rocminfo"]),
            "git_revision": _command_output(["git", "rev-parse", "HEAD"]),
        },
        notes=[
            "Prepared only; run the candidate offline on this system and complete every measurement "
            "and check."
        ],
    )


def readiness_failures(record: ProbeRecord) -> list[str]:
    failures: list[str] = []
    if not record.candidate.licence_reviewed:
        failures.append("licence review is incomplete")
    missing_measurements = [
        name for name, value in record.measurements.model_dump().items() if value is None
    ]
    if missing_measurements:
        failures.append(f"measurements are incomplete: {', '.join(missing_measurements)}")
    failed_checks = [name for name, value in record.checks.model_dump().items() if not value]
    if failed_checks:
        failures.append(f"readiness checks failed or are incomplete: {', '.join(failed_checks)}")
    return failures


def load_probe_record(path: Path) -> ProbeRecord:
    return ProbeRecord.model_validate_json(path.read_text(encoding="utf-8"))


def _command_output(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {type(error).__name__}"
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if command[0] == "rocminfo":
        allowed = ("Name:", "Marketing Name:", "Vendor Name:", "Device Type:", "Runtime Version:")
        output = "\n".join(line.strip() for line in output.splitlines() if line.strip().startswith(allowed))
    return output[:12_000] or f"no output (exit {completed.returncode})"
