import subprocess
import sys
from array import array

import pytest
from speechshift.voice_transform_probe import (
    PRIMARY_STYLE_SEED,
    REQUIRED_CORPUS_SIZE,
    SAMPLE_RATE,
    TransformObservation,
    build_synthetic_corpus,
    run_in_memory_probe,
    terminate_worker,
)


def pcm(seconds: float, value: int = 1_000) -> bytes:
    return array("h", [value] * round(SAMPLE_RATE * seconds)).tobytes()


class FakeTransform:
    def transform(self, input_pcm: bytes, sample_rate: int, style_seed: int) -> TransformObservation:
        assert sample_rate == SAMPLE_RATE
        source = array("h")
        source.frombytes(input_pcm)
        offset = 100 if style_seed == PRIMARY_STYLE_SEED else -100
        output = array("h", (sample // 2 + offset for sample in source))
        return TransformObservation(
            output_pcm=output.tobytes(),
            phoneme_error_rate_percent=5.0,
            speaker_cosine_similarity=0.5,
        )


def test_in_memory_probe_aggregates_safe_metrics_without_files(tmp_path) -> None:
    corpus = [pcm(0.25 + index * 0.05) for index in range(REQUIRED_CORPUS_SIZE - 1)]
    corpus.append(pcm(8))
    summary = run_in_memory_probe(FakeTransform(), corpus, tmp_path)
    assert summary.input_duration_ms == 8_000
    assert summary.phoneme_error_rate_percent == 5.0
    assert summary.max_speaker_cosine_similarity == 0.5
    assert summary.output_duration_ratio == 1.0
    assert summary.clipped_sample_percent == 0
    assert summary.deterministic_seed_passed is True
    assert summary.distinct_seed_passed is True
    assert summary.in_memory_only_passed is True
    assert list(tmp_path.iterdir()) == []


def test_in_memory_probe_requires_twelve_samples_and_eight_second_input(tmp_path) -> None:
    with pytest.raises(ValueError, match="12 samples"):
        run_in_memory_probe(FakeTransform(), [pcm(8)], tmp_path)
    with pytest.raises(ValueError, match="eight-second"):
        run_in_memory_probe(FakeTransform(), [pcm(1)] * REQUIRED_CORPUS_SIZE, tmp_path)


def test_espeak_corpus_is_memory_only_and_includes_maximum_input(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = build_synthetic_corpus()
    assert len(corpus) == REQUIRED_CORPUS_SIZE
    assert max(len(sample) for sample in corpus) == SAMPLE_RATE * 8 * 2
    assert all(sample and len(sample) % 2 == 0 for sample in corpus)
    assert list(tmp_path.iterdir()) == []


def test_worker_termination_meets_cancellation_deadline() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert terminate_worker(process) <= 250
    assert process.poll() is not None
