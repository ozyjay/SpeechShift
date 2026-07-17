from pathlib import Path

from speechshift.model_readiness import (
    CandidateArtifact,
    CandidateManifest,
    ProbeMeasurements,
    ProbeRecord,
    ReadinessChecks,
    VoiceTransformChecks,
    VoiceTransformMeasurements,
    candidate_licence_failures,
    readiness_failures,
)


def candidate(**overrides: object) -> CandidateManifest:
    values: dict[str, object] = {
        "candidate_id": "candidate",
        "capability": "speech.recognise",
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


def complete_voice_transform_record(**measurement_overrides: object) -> ProbeRecord:
    voice_measurements: dict[str, object] = {
        "phoneme_error_rate_percent": 8.0,
        "max_speaker_cosine_similarity": 0.65,
        "output_duration_ratio": 1.0,
        "clipped_sample_percent": 0.0,
    }
    voice_measurements.update(measurement_overrides)
    return ProbeRecord(
        created_at="2026-07-17T00:00:00Z",
        candidate=candidate(capability="speech.voice_transform"),
        system={"platform": "Fedora 44"},
        measurements=ProbeMeasurements(
            input_duration_ms=8_000,
            load_time_ms=10_000,
            first_audio_latency_ms=2_500,
            total_latency_ms=2_500,
            cancellation_latency_ms=100,
            peak_process_rss_mb=8_000,
            peak_vram_mb=6_000,
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
        voice_transform_measurements=VoiceTransformMeasurements(**voice_measurements),
        voice_transform_checks=VoiceTransformChecks(
            synthetic_corpus_only=True,
            in_memory_only_passed=True,
            no_target_voice_passed=True,
            content_preservation_passed=True,
            anonymisation_passed=True,
            audio_safety_passed=True,
            deterministic_seed_passed=True,
            distinct_seed_passed=True,
        ),
    )


def test_voice_transform_record_passes_capability_thresholds() -> None:
    assert readiness_failures(complete_voice_transform_record()) == []


def test_voice_transform_record_fails_closed_without_capability_evidence() -> None:
    record = complete_voice_transform_record()
    record.voice_transform_measurements = None
    record.voice_transform_checks = None
    failures = readiness_failures(record)
    assert "voice-transform measurements are missing" in failures
    assert "voice-transform checks are missing" in failures


def test_voice_transform_record_enforces_quality_thresholds() -> None:
    record = complete_voice_transform_record(
        phoneme_error_rate_percent=10.1,
        max_speaker_cosine_similarity=0.71,
        output_duration_ratio=1.21,
        clipped_sample_percent=0.01,
    )
    failures = readiness_failures(record)
    assert "phoneme error rate exceeds 10 percent" in failures
    assert "speaker cosine similarity exceeds 0.70" in failures
    assert "output duration ratio is outside 0.8 to 1.2" in failures
    assert "output contains clipped samples" in failures


def test_voice_transform_record_enforces_operational_thresholds() -> None:
    record = complete_voice_transform_record()
    record.measurements.first_audio_latency_ms = 3_001
    record.measurements.total_latency_ms = 3_001
    record.measurements.cancellation_latency_ms = 251
    record.measurements.peak_process_rss_mb = 16_385
    record.measurements.peak_vram_mb = 12_289
    failures = readiness_failures(record)
    assert "first-audio latency exceeds 3000 ms" in failures
    assert "total latency exceeds 3000 ms" in failures
    assert "cancellation latency exceeds 250 ms" in failures
    assert "peak process RSS exceeds 16384 MB" in failures
    assert "peak GPU allocation exceeds 12288 MB" in failures


def test_unreviewed_checkpoint_licence_blocks_readiness() -> None:
    record = complete_voice_transform_record()
    record.candidate.artifacts = [
        CandidateArtifact(
            name="checkpoint.zip",
            source="https://example.invalid/checkpoint.zip",
            licence="not stated",
            licence_reviewed=False,
        )
    ]
    assert "artefact licence review is incomplete: checkpoint.zip" in readiness_failures(record)


def test_schema_version_one_record_remains_readable() -> None:
    record = ProbeRecord.model_validate(
        {
            "schema_version": 1,
            "created_at": "2026-07-17T00:00:00Z",
            "candidate": candidate().model_dump(),
            "system": {},
        }
    )
    assert record.schema_version == 1
    assert record.voice_transform_measurements is None
    assert record.voice_transform_checks is None


def test_voiceprivacy_b3_manifest_is_pinned_and_download_blocked() -> None:
    manifest = CandidateManifest.model_validate_json(
        Path("docs/model_candidates/voiceprivacy-2026-b3-sttts-rocm.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest.revision == "e6810a4764d12a25ca7e82124da86b707d52e5d5"
    assert manifest.capability == "speech.voice_transform"
    assert [artifact.name for artifact in manifest.artifacts] == [
        "anonymization.zip",
        "asr.zip",
        "tts.zip",
    ]
    assert candidate_licence_failures(manifest) == [
        "licence review is incomplete",
        "artefact licence review is incomplete: anonymization.zip, asr.zip, tts.zip",
    ]
