from __future__ import annotations


class AudioStreamError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SequencedPcmBuffer:
    HEADER_BYTES = 4

    def __init__(self, maximum_audio_bytes: int) -> None:
        if maximum_audio_bytes < 1:
            raise ValueError("maximum_audio_bytes must be positive")
        self._maximum_audio_bytes = maximum_audio_bytes
        self._chunks: list[bytes] = []
        self._length = 0
        self._next_sequence = 1

    @property
    def length(self) -> int:
        return self._length

    @property
    def frame_count(self) -> int:
        return self._next_sequence - 1

    def append(self, frame: bytes) -> None:
        if len(frame) <= self.HEADER_BYTES:
            raise AudioStreamError("invalid_audio_frame")
        sequence = int.from_bytes(frame[: self.HEADER_BYTES], byteorder="little", signed=False)
        if sequence != self._next_sequence:
            raise AudioStreamError("audio_sequence_error")
        audio = frame[self.HEADER_BYTES :]
        if self._length + len(audio) > self._maximum_audio_bytes:
            raise AudioStreamError("audio_buffer_limit")
        self._chunks.append(audio)
        self._length += len(audio)
        self._next_sequence += 1

    def consume(self) -> bytes:
        output = b"".join(self._chunks)
        self.clear()
        return output

    def clear(self) -> None:
        self._chunks.clear()
        self._length = 0
        self._next_sequence = 1

