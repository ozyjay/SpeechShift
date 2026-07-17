from __future__ import annotations

import io
import subprocess
import sys
import time
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SAMPLE_RATE = 16_000
SAMPLE_WIDTH_BYTES = 2
REQUIRED_CORPUS_SIZE = 12
PRIMARY_STYLE_SEED = 17_071
SECONDARY_STYLE_SEED = 93_217


@dataclass(frozen=True, slots=True)
class TransformObservation:
    output_pcm: bytes
    phoneme_error_rate_percent: float
    speaker_cosine_similarity: float


class InMemoryVoiceTransform(Protocol):
    def transform(self, input_pcm: bytes, sample_rate: int, style_seed: int) -> TransformObservation:
        """Transform PCM without accepting paths, target audio or transcript text."""


@dataclass(frozen=True, slots=True)
class VoiceTransformProbeSummary:
    input_duration_ms: int
    maximum_latency_ms: int
    phoneme_error_rate_percent: float
    max_speaker_cosine_similarity: float
    output_duration_ratio: float
    clipped_sample_percent: float
    deterministic_seed_passed: bool
    distinct_seed_passed: bool
    in_memory_only_passed: bool


def run_in_memory_probe(
    adapter: InMemoryVoiceTransform,
    corpus: list[bytes],
    watched_directory: Path,
) -> VoiceTransformProbeSummary:
    if len(corpus) != REQUIRED_CORPUS_SIZE:
        raise ValueError(f"voice-transform corpus must contain {REQUIRED_CORPUS_SIZE} samples")
    for pcm in corpus:
        _validate_pcm16(pcm)
    longest = max(corpus, key=len)
    if _duration_ms(longest) != 8_000:
        raise ValueError("voice-transform corpus must include an eight-second sample")

    before_files = _relative_files(watched_directory)
    latencies: list[int] = []
    phoneme_error_rates: list[float] = []
    similarities: list[float] = []
    duration_ratios: list[float] = []
    clipped_percentages: list[float] = []
    longest_primary: TransformObservation | None = None

    for input_pcm in corpus:
        started = time.perf_counter()
        observation = adapter.transform(input_pcm, SAMPLE_RATE, PRIMARY_STYLE_SEED)
        latencies.append(round((time.perf_counter() - started) * 1_000))
        _validate_observation(observation)
        phoneme_error_rates.append(observation.phoneme_error_rate_percent)
        similarities.append(observation.speaker_cosine_similarity)
        duration_ratios.append(len(observation.output_pcm) / len(input_pcm))
        clipped_percentages.append(_clipped_sample_percent(observation.output_pcm))
        if input_pcm is longest:
            longest_primary = observation

    if longest_primary is None:
        raise RuntimeError("longest synthetic sample was not probed")
    repeated = adapter.transform(longest, SAMPLE_RATE, PRIMARY_STYLE_SEED)
    alternate = adapter.transform(longest, SAMPLE_RATE, SECONDARY_STYLE_SEED)
    _validate_observation(repeated)
    _validate_observation(alternate)
    after_files = _relative_files(watched_directory)

    return VoiceTransformProbeSummary(
        input_duration_ms=8_000,
        maximum_latency_ms=max(latencies),
        phoneme_error_rate_percent=sum(phoneme_error_rates) / len(phoneme_error_rates),
        max_speaker_cosine_similarity=max(similarities),
        output_duration_ratio=max(duration_ratios, key=lambda ratio: abs(1 - ratio)),
        clipped_sample_percent=max(clipped_percentages),
        deterministic_seed_passed=longest_primary.output_pcm == repeated.output_pcm,
        distinct_seed_passed=longest_primary.output_pcm != alternate.output_pcm,
        in_memory_only_passed=before_files == after_files,
    )


def build_synthetic_corpus() -> list[bytes]:
    specifications = [
        ("en-au", 135, "Speech Shift changes vocal characteristics while keeping the spoken words."),
        ("en-au", 155, "A visitor can compare the original recording with an artificial result."),
        ("en-au", 175, "Local processing keeps this demonstration independent of the internet."),
        ("en-au", 145, "Clear speech should remain understandable after the voice is anonymised."),
        ("en-au", 165, "The quick brown fox jumps over the lazy dog near the river bank."),
        ("en-au", 125, "Numbers such as seven, twenty four and ninety should remain clear."),
        ("en-au", 185, "Short phrases test whether rapid speech remains intelligible."),
        ("en-au", 115, "A slower sentence checks rhythm, pauses and stable output duration."),
        ("en-gb", 140, "Synthetic input prevents the probe from using an identifiable person's voice."),
        ("en-gb", 170, "Different speaking rates exercise the phonetic content pathway."),
        ("en-us", 150, "The model must never accept a visitor supplied target recording."),
        (
            "en-au",
            130,
            "This final maximum length sample checks a complete eight second recording while the "
            "system preserves every phrase, releases memory, and remains ready to cancel safely.",
        ),
    ]
    maximum_bytes = SAMPLE_RATE * 8 * SAMPLE_WIDTH_BYTES
    corpus = [_espeak_pcm(voice, speed, text)[:maximum_bytes] for voice, speed, text in specifications]
    corpus[-1] = _fit_duration(corpus[-1], 8_000)
    return corpus


def terminate_worker(process: subprocess.Popen[bytes], deadline_ms: int = 250) -> int:
    if process.poll() is not None:
        return 0
    started = time.perf_counter()
    process.terminate()
    try:
        process.wait(timeout=deadline_ms / 1_000)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    return round((time.perf_counter() - started) * 1_000)


def _espeak_pcm(voice: str, speed: int, text: str) -> bytes:
    completed = subprocess.run(
        ["espeak-ng", "--stdout", "-v", voice, "-s", str(speed), text],
        capture_output=True,
        timeout=20,
        check=True,
    )
    with wave.open(io.BytesIO(completed.stdout), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != SAMPLE_WIDTH_BYTES:
            raise ValueError("eSpeak probe audio must be mono PCM16")
        source_rate = audio.getframerate()
        source_pcm = audio.readframes(audio.getnframes())
    return _resample_pcm16(source_pcm, source_rate, SAMPLE_RATE)


def _resample_pcm16(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    _validate_pcm16(pcm)
    if source_rate == target_rate:
        return pcm
    source = array("h")
    source.frombytes(pcm)
    if sys.byteorder != "little":
        source.byteswap()
    output_length = round(len(source) * target_rate / source_rate)
    output = array("h")
    for index in range(output_length):
        position = index * source_rate / target_rate
        before = min(int(position), len(source) - 1)
        after = min(before + 1, len(source) - 1)
        fraction = position - before
        output.append(round(source[before] * (1 - fraction) + source[after] * fraction))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def _fit_duration(pcm: bytes, duration_ms: int) -> bytes:
    target_bytes = round(SAMPLE_RATE * duration_ms / 1_000) * SAMPLE_WIDTH_BYTES
    return pcm[:target_bytes].ljust(target_bytes, b"\x00")


def _validate_observation(observation: TransformObservation) -> None:
    _validate_pcm16(observation.output_pcm)
    if not 0 <= observation.phoneme_error_rate_percent <= 100:
        raise ValueError("phoneme error rate must be between zero and 100")
    if not -1 <= observation.speaker_cosine_similarity <= 1:
        raise ValueError("speaker cosine similarity must be between minus one and one")


def _validate_pcm16(pcm: bytes) -> None:
    if not pcm or len(pcm) % SAMPLE_WIDTH_BYTES:
        raise ValueError("probe audio must contain complete mono PCM16 samples")


def _duration_ms(pcm: bytes) -> int:
    return round(len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH_BYTES) * 1_000)


def _clipped_sample_percent(pcm: bytes) -> float:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    clipped = sum(sample in {-32_768, 32_767} for sample in samples)
    return clipped / len(samples) * 100


def _relative_files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
