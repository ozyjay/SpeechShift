from __future__ import annotations

import asyncio
import json

import httpx
from websockets.asyncio.client import connect

BASE_URL = "http://127.0.0.1:3800"
WEBSOCKET_URL = "ws://127.0.0.1:3800"


async def run() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5) as client:
        selected = await client.post("/api/providers/select", json={"provider": "mock-modeldeck"})
        selected.raise_for_status()
        session_id = (await client.post("/api/sessions")).raise_for_status().json()["session_id"]
        event_types: list[str] = []
        output_sequences: list[int] = []
        try:
            async with connect(f"{WEBSOCKET_URL}/ws/sessions/{session_id}", max_size=2_500_000) as socket:
                await socket.send(
                    json.dumps(
                        {
                            "command": "start_mock",
                            "request": {
                                "mode": "language",
                                "sentence_id": "campus",
                                "selection_id": "fr",
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
                    await socket.send(sequence.to_bytes(4, "little") + b"\x00\x00" * 320)
                await socket.send(json.dumps({"command": "end_audio"}))
                while True:
                    message = await asyncio.wait_for(socket.recv(), timeout=5)
                    if isinstance(message, bytes):
                        output_sequences.append(int.from_bytes(message[:4], "little"))
                        continue
                    event = json.loads(message)
                    event_types.append(event["type"])
                    if event["type"] == "complete":
                        break
                    if event["type"] == "error":
                        raise RuntimeError(f"mock pipeline error: {event['code']}")
        finally:
            await client.delete(f"/api/sessions/{session_id}")
            await client.post("/api/providers/select", json={"provider": "replay"})

    required = {
        "transcript_partial",
        "transcript_final",
        "translation_final",
        "audio_start",
        "audio_end",
        "complete",
    }
    if not required.issubset(event_types):
        raise RuntimeError(f"mock pipeline omitted required events: {required.difference(event_types)}")
    if not output_sequences or output_sequences != list(range(1, len(output_sequences) + 1)):
        raise RuntimeError("mock output audio sequence was empty or invalid")


if __name__ == "__main__":
    asyncio.run(run())
