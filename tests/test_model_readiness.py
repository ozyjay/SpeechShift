from pathlib import Path

from speechshift.model_readiness import (
    CandidateManifest,
    ProbeMeasurements,
    ProbeRecord,
    ReadinessChecks,
    readiness_failures,
)


def candidate(**overrides: object) -> CandidateManifest:
    values: dict[str, object] = {
        "candidate_id": "candidate",
        "capability": "speech.voice_transform",
        "repository": "https://example.invalid/repository",
        "revision": "abc123",
        "model_id": "model",
        "licence": "example",
        "licence_reviewed": True,
        "parameters": "1B",
        "precision": "fp16",
        "languages": ["English"],
        "framework": "example 1.0",
        "cuda_or_triton_requirements": "none",
        "maintenance_status": "maintained",
    }
    values.update(overrides)
    return CandidateManifest(**values)


def test_incomplete_probe_cannot_be_promoted() -> None:
    record = ProbeRecord(created_at="2026-07-17T00:00:00Z", candidate=candidate(), system={})
    failures = readiness_failures(record)
    assert any("measurements are incomplete" in failure for failure in failures)
    assert any("readiness checks" in failure for failure in failures)


def test_complete_probe_passes_all_recorded_gates() -> None:
    record = ProbeRecord(
        created_at="2026-07-17T00:00:00Z",
        candidate=candidate(),
        system={"platform": "Fedora 44"},
        measurements=ProbeMeasurements(
            input_duration_ms=2_000,
            load_time_ms=1_000,
            first_audio_latency_ms=300,
            total_latency_ms=2_200,
            cancellation_latency_ms=50,
            peak_process_rss_mb=2_000,
            peak_vram_mb=4_000,
        ),
        checks=ReadinessChecks(
            rocm_probe_passed=True,
            offline_run_passed=True,
            streaming_passed=True,
            cancellation_passed=True,
            latency_accepted=True,
            memory_fit_passed=True,
            memory_released=True,
            clean_shutdown_passed=True,
            public_output_reviewed=True,
        ),
    )
    assert readiness_failures(record) == []


def test_example_candidate_manifest_stays_valid() -> None:
    CandidateManifest.model_validate_json(
        Path("docs/model_candidate.example.json").read_text(encoding="utf-8")
    )
