import pytest
from speechshift.streaming import AudioStreamError, SequencedPcmBuffer


def frame(sequence: int, audio: bytes = b"\x00\x00") -> bytes:
    return sequence.to_bytes(4, "little") + audio


def test_sequenced_pcm_buffer_is_ordered_and_bounded() -> None:
    buffer = SequencedPcmBuffer(maximum_audio_bytes=4)
    buffer.append(frame(1))
    buffer.append(frame(2))
    assert buffer.frame_count == 2
    assert buffer.consume() == b"\x00\x00\x00\x00"
    assert buffer.length == 0


def test_sequenced_pcm_buffer_rejects_gaps_and_overflow() -> None:
    buffer = SequencedPcmBuffer(maximum_audio_bytes=2)
    with pytest.raises(AudioStreamError, match="audio_sequence_error"):
        buffer.append(frame(2))
    buffer.append(frame(1))
    with pytest.raises(AudioStreamError, match="audio_buffer_limit"):
        buffer.append(frame(2))

