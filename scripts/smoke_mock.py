from __future__ import annotations

import asyncio
import json

import httpx
from websockets.asyncio.client import connect

BASE_URL = "http://127.0.0.1:3800"
WEBSOCKET_URL = "ws://127.0.0.1:3800"
INPUT_AUDIO = (1_000).to_bytes(2, "little", signed=True) * 320


async def exercise_stream(
    client: httpx.AsyncClient,
    provider: str,
    command: str,
    mode: str,
    selection_id: str,
) -> tuple[list[str], list[int], bytes]:
    (await client.post("/api/providers/select", json={"provider": provider})).raise_for_status()
    session_id = (await client.post("/api/sessions")).raise_for_status().json()["session_id"]
    event_types: list[str] = []
    output_sequences: list[int] = []
    output_audio: list[bytes] = []
    try:
        async with connect(f"{WEBSOCKET_URL}/ws/sessions/{session_id}", max_size=2_500_000) as socket:
            await socket.send(
                json.dumps(
                    {
                        "command": command,
                        "request": {
                            "mode": mode,
                            "sentence_id": "campus",
                            "selection_id": selection_id,
                            "audio_format": {
                                "encoding": "pcm_s16le",
                                "sample_rate_hz": 16_000,
                                "channels": 1,
                            },
                        },
                    }
                )
            )
            for sequence in range(1, 7):
                await socket.send(sequence.to_bytes(4, "little") + INPUT_AUDIO)
            await socket.send(json.dumps({"command": "end_audio"}))
            while True:
                message = await asyncio.wait_for(socket.recv(), timeout=5)
                if isinstance(message, bytes):
                    output_sequences.append(int.from_bytes(message[:4], "little"))
                    output_audio.append(message[4:])
                    continue
                event = json.loads(message)
                event_types.append(event["type"])
                if event["type"] == "complete":
                    break
                if event["type"] == "error":
                    raise RuntimeError(f"{provider} pipeline error: {event['code']}")
    finally:
        await client.delete(f"/api/sessions/{session_id}")
    return event_types, output_sequences, b"".join(output_audio)


def assert_ordered_output(sequences: list[int], provider: str) -> None:
    if not sequences or sequences != list(range(1, len(sequences) + 1)):
        raise RuntimeError(f"{provider} output audio sequence was empty or invalid")


async def run() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5) as client:
        try:
            mock_events, mock_sequences, _ = await exercise_stream(
                client,
                provider="mock-modeldeck",
                command="start_mock",
                mode="language",
                selection_id="fr",
            )
            required_mock = {
                "transcript_partial",
                "transcript_final",
                "translation_final",
                "audio_start",
                "audio_end",
                "complete",
            }
            if not required_mock.issubset(mock_events):
                raise RuntimeError(
                    f"mock pipeline omitted required events: {required_mock.difference(mock_events)}"
                )
            assert_ordered_output(mock_sequences, "mock")

            local_events, local_sequences, local_audio = await exercise_stream(
                client,
                provider="local",
                command="start_local",
                mode="voice",
                selection_id="robot",
            )
            required_local = {"audio_start", "audio_end", "metrics", "complete"}
            if not required_local.issubset(local_events):
                raise RuntimeError(
                    f"local DSP omitted required events: {required_local.difference(local_events)}"
                )
            assert_ordered_output(local_sequences, "local DSP")
            if local_audio == INPUT_AUDIO * 6:
                raise RuntimeError("local DSP returned unchanged input")
        finally:
            await client.post("/api/providers/select", json={"provider": "replay"})


if __name__ == "__main__":
    asyncio.run(run())

