import math
import sys
from array import array

import pytest
from speechshift.audio_activity import analyse_pcm16_activity


def pcm_constant(sample: int, milliseconds: int, sample_rate: int = 16_000) -> bytes:
    samples = array("h", [sample] * round(sample_rate * milliseconds / 1_000))
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def test_silence_is_rejected_without_exposing_audio() -> None:
    activity = analyse_pcm16_activity(pcm_constant(0, 500), 16_000)
    assert activity.duration_ms == 500
    assert activity.active_ms == 0
    assert activity.peak_dbfs == -120.0
    assert activity.rms_dbfs == -120.0
    assert activity.has_speech is False


def test_sustained_audible_input_passes() -> None:
    activity = analyse_pcm16_activity(pcm_constant(1_000, 200), 16_000)
    assert activity.active_ms == 200
    assert activity.peak_dbfs == pytest.approx(20 * math.log10(1_000 / 32768), abs=0.1)
    assert activity.has_speech is True


def test_short_noise_does_not_count_as_usable_input() -> None:
    pcm = pcm_constant(1_000, 100) + pcm_constant(0, 400)
    assert analyse_pcm16_activity(pcm, 16_000).has_speech is False


def test_activity_rejects_malformed_pcm() -> None:
    with pytest.raises(ValueError, match="complete samples"):
        analyse_pcm16_activity(b"\x01", 16_000)
