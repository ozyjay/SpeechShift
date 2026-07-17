from __future__ import annotations

import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class CandidateArtifact(BaseModel):
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    licence_source: str | None = None
    licence_reviewed: bool = False
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


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
    artifacts: list[CandidateArtifact] = Field(default_factory=list)


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


class VoiceTransformMeasurements(BaseModel):
    phoneme_error_rate_percent: float | None = Field(default=None, ge=0, le=100)
    max_speaker_cosine_similarity: float | None = Field(default=None, ge=-1, le=1)
    output_duration_ratio: float | None = Field(default=None, gt=0)
    clipped_sample_percent: float | None = Field(default=None, ge=0, le=100)


class VoiceTransformChecks(BaseModel):
    synthetic_corpus_only: bool = False
    in_memory_only_passed: bool = False
    no_target_voice_passed: bool = False
    content_preservation_passed: bool = False
    anonymisation_passed: bool = False
    audio_safety_passed: bool = False
    deterministic_seed_passed: bool = False
    distinct_seed_passed: bool = False


class ProbeRecord(BaseModel):
    schema_version: int = 2
    created_at: str
    candidate: CandidateManifest
    system: dict[str, str]
    measurements: ProbeMeasurements = Field(default_factory=ProbeMeasurements)
    checks: ReadinessChecks = Field(default_factory=ReadinessChecks)
    voice_transform_measurements: VoiceTransformMeasurements | None = None
    voice_transform_checks: VoiceTransformChecks | None = None
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


def candidate_licence_failures(candidate: CandidateManifest) -> list[str]:
    failures: list[str] = []
    if not candidate.licence_reviewed:
        failures.append("licence review is incomplete")
    unreviewed_artifacts = [
        artifact.name for artifact in candidate.artifacts if not artifact.licence_reviewed
    ]
    if unreviewed_artifacts:
        failures.append(f"artefact licence review is incomplete: {', '.join(unreviewed_artifacts)}")
    return failures


def readiness_failures(record: ProbeRecord) -> list[str]:
    failures = candidate_licence_failures(record.candidate)
    missing_measurements = [
        name for name, value in record.measurements.model_dump().items() if value is None
    ]
    if missing_measurements:
        failures.append(f"measurements are incomplete: {', '.join(missing_measurements)}")
    failed_checks = [name for name, value in record.checks.model_dump().items() if not value]
    if failed_checks:
        failures.append(f"readiness checks failed or are incomplete: {', '.join(failed_checks)}")
    if record.candidate.capability == "speech.voice_transform":
        failures.extend(_voice_transform_failures(record))
    return failures


def _voice_transform_failures(record: ProbeRecord) -> list[str]:
    measurements = record.voice_transform_measurements
    checks = record.voice_transform_checks
    failures: list[str] = []
    if measurements is None:
        failures.append("voice-transform measurements are missing")
    else:
        missing = [name for name, value in measurements.model_dump().items() if value is None]
        if missing:
            failures.append(f"voice-transform measurements are incomplete: {', '.join(missing)}")
        if (
            measurements.phoneme_error_rate_percent is not None
            and measurements.phoneme_error_rate_percent > 10
        ):
            failures.append("phoneme error rate exceeds 10 percent")
        if (
            measurements.max_speaker_cosine_similarity is not None
            and measurements.max_speaker_cosine_similarity > 0.70
        ):
            failures.append("speaker cosine similarity exceeds 0.70")
        if measurements.output_duration_ratio is not None and not (
            0.8 <= measurements.output_duration_ratio <= 1.2
        ):
            failures.append("output duration ratio is outside 0.8 to 1.2")
        if measurements.clipped_sample_percent is not None and measurements.clipped_sample_percent > 0:
            failures.append("output contains clipped samples")
    if checks is None:
        failures.append("voice-transform checks are missing")
    else:
        failed = [name for name, value in checks.model_dump().items() if not value]
        if failed:
            failures.append(f"voice-transform checks failed or are incomplete: {', '.join(failed)}")
    if record.measurements.first_audio_latency_ms is not None:
        if record.measurements.first_audio_latency_ms > 3_000:
            failures.append("first-audio latency exceeds 3000 ms")
    if record.measurements.total_latency_ms is not None:
        if record.measurements.total_latency_ms > 3_000:
            failures.append("total latency exceeds 3000 ms")
    if record.measurements.cancellation_latency_ms is not None:
        if record.measurements.cancellation_latency_ms > 250:
            failures.append("cancellation latency exceeds 250 ms")
    if record.measurements.peak_process_rss_mb is not None:
        if record.measurements.peak_process_rss_mb > 16_384:
            failures.append("peak process RSS exceeds 16384 MB")
    if record.measurements.peak_vram_mb is not None:
        if record.measurements.peak_vram_mb > 12_288:
            failures.append("peak GPU allocation exceeds 12288 MB")
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
