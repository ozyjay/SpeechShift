import asyncio
import math
import sys
from array import array

import pytest
from speechshift.local_dsp import PROFILE_LABELS, LocalDspProvider, transform_pcm16
from speechshift.models import MockRunRequest
from speechshift.sessions import Session


def sine_pcm(frequency: float, sample_rate: int = 16_000, seconds: float = 0.25) -> bytes:
    samples = array(
        "h",
        (
            round(math.sin(2 * math.pi * frequency * index / sample_rate) * 16_000)
            for index in range(round(sample_rate * seconds))
        ),
    )
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


@pytest.mark.parametrize("profile", list(PROFILE_LABELS))
def test_dsp_profiles_are_bounded_and_change_audio(profile: str) -> None:
    original = sine_pcm(220)
    transformed = transform_pcm16(original, 16_000, profile)
    samples = array("h")
    samples.frombytes(transformed)
    if sys.byteorder != "little":
        samples.byteswap()
    assert transformed != original
    assert max(abs(sample) for sample in samples) <= round(0.82 * 32767) + 1
    assert samples[0] == 0
    assert samples[-1] == 0


def test_pitch_profiles_change_duration_in_expected_direction() -> None:
    original = sine_pcm(220)
    assert len(transform_pcm16(original, 16_000, "calm-narrator")) > len(original)
    assert len(transform_pcm16(original, 16_000, "energetic-presenter")) < len(original)
    assert len(transform_pcm16(original, 16_000, "robot")) == len(original)


def test_local_provider_streams_real_processed_pcm() -> None:
    async def scenario() -> None:
        events: list[dict[str, object]] = []
        frames: list[bytes] = []

        async def send_json(event: dict[str, object]) -> None:
            events.append(event)

        async def send_bytes(frame: bytes) -> None:
            frames.append(frame)

        source = sine_pcm(220, seconds=0.5)
        await LocalDspProvider().run(
            Session(id="local-session"),
            MockRunRequest(
                mode="voice",
                sentence_id="campus",
                selection_id="robot",
                audio_format={"encoding": "pcm_s16le", "sample_rate_hz": 16_000, "channels": 1},
            ),
            input_pcm=source,
            input_frames=25,
            send_json=send_json,
            send_bytes=send_bytes,
        )
        assert [event["type"] for event in events] == [
            "state",
            "state",
            "audio_start",
            "audio_end",
            "metrics",
            "complete",
        ]
        assert all(event["dsp"] is True for event in events)
        output = b"".join(frame[4:] for frame in frames)
        assert output != source
        assert [int.from_bytes(frame[:4], "little") for frame in frames] == list(
            range(1, len(frames) + 1)
        )

    asyncio.run(scenario())

