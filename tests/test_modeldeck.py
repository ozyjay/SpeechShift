import asyncio
import io
import json
import wave

import httpx
import pytest
from speechshift.modeldeck import MODELDECK_VOICES, ModelDeckError, ModelDeckGateway, ModelDeckProvider
from speechshift.models import ModelDeckRunRequest
from speechshift.sessions import Session


def _wav_bytes(pcm: bytes = b"\x00\x01" * 4_000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24_000)
        audio.writeframes(pcm)
    return output.getvalue()


def _gateway(handler: httpx.AsyncBaseTransport) -> ModelDeckGateway:
    return ModelDeckGateway(
        "http://127.0.0.1:8600",
        stt_timeout_seconds=2,
        translation_timeout_seconds=2,
        tts_timeout_seconds=10,
        transport=handler,
    )


def test_readiness_requires_every_speechshift_route() -> None:
    async def scenario() -> None:
        routes = [
            {"public_name": "speechshift-stt", "ready": True},
            {"public_name": "speechshift-en-fr", "ready": True},
            {"public_name": "speechshift-en-de", "ready": True},
            {"public_name": "speechshift-voice", "ready": True},
        ]

        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/routes"
            return httpx.Response(200, json={"routes": routes})

        gateway = _gateway(httpx.MockTransport(handler))
        assert await gateway.ready() is True
        routes[-1]["ready"] = False
        assert await gateway.ready() is False
        await gateway.close()

    asyncio.run(scenario())


def test_language_pipeline_uses_stt_translation_and_tts_contracts() -> None:
    async def scenario() -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            calls.append((request.url.path, payload))
            if request.url.path == "/v1/audio/transcriptions":
                return httpx.Response(200, json={"text": "Welcome to JCU Open Day."})
            if request.url.path == "/v1/translations":
                return httpx.Response(200, json={"output_text": "Bienvenue à JCU Open Day."})
            if request.url.path == "/v1/audio/speech":
                return httpx.Response(200, content=_wav_bytes())
            raise AssertionError(f"unexpected path {request.url.path}")

        gateway = _gateway(httpx.MockTransport(handler))
        provider = ModelDeckProvider(gateway, pipeline_timeout_seconds=30)
        request = ModelDeckRunRequest.model_validate(
            {
                "mode": "language",
                "selection_id": "fr",
                "audio_format": {
                    "encoding": "pcm_s16le",
                    "sample_rate_hz": 16_000,
                    "channels": 1,
                },
            }
        )
        events: list[dict[str, object]] = []
        frames: list[bytes] = []

        async def send_json(event: dict[str, object]) -> None:
            events.append(event)

        async def send_bytes(frame: bytes) -> None:
            frames.append(frame)

        await provider.run(
            Session(id="test-session"),
            request,
            b"\x00\x10" * 3_200,
            2,
            send_json,
            send_bytes,
        )

        assert [path for path, _ in calls] == [
            "/v1/audio/transcriptions",
            "/v1/translations",
            "/v1/audio/speech",
        ]
        assert calls[0][1] == {
            "request_id": calls[0][1]["request_id"],
            "model": "speechshift-stt",
            "language": "en",
            "encoding": "pcm_s16le",
            "sample_rate_hz": 16_000,
            "channels": 1,
            "audio_base64": calls[0][1]["audio_base64"],
        }
        assert isinstance(calls[0][1]["audio_base64"], str)
        assert calls[1][1]["model"] == "speechshift-en-fr"
        assert calls[2][1] == {
            "request_id": calls[2][1]["request_id"],
            "model": "speechshift-voice",
            "input": "Bienvenue à JCU Open Day.",
            "voice": "ryan",
            "language": "fr",
            "response_format": "wav",
        }
        assert [event["type"] for event in events] == [
            "state",
            "transcript_final",
            "state",
            "translation_final",
            "state",
            "audio_start",
            "audio_end",
            "metrics",
            "complete",
        ]
        assert all(event["modeldeck"] is True for event in events)
        assert frames and int.from_bytes(frames[0][:4], "little") == 1
        await gateway.close()

    asyncio.run(scenario())


def test_gateway_accepts_only_the_four_curated_modeldeck_voices() -> None:
    async def scenario() -> None:
        requests: list[dict[str, object]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            return httpx.Response(200, content=_wav_bytes())

        gateway = _gateway(httpx.MockTransport(handler))
        for voice in MODELDECK_VOICES:
            pcm, sample_rate = await gateway.synthesise(
                f"voice-{voice}",
                "The service is ready.",
                voice=voice,
                language="en",
            )
            assert pcm
            assert sample_rate == 24_000

        assert [request["voice"] for request in requests] == [
            "ryan",
            "aiden",
            "vivian",
            "serena",
        ]
        with pytest.raises(ModelDeckError, match="unsupported_voice"):
            await gateway.synthesise(
                "voice-unsupported",
                "The service is ready.",
                voice="ono_anna",
                language="en",
            )
        assert len(requests) == 4
        await gateway.close()

    asyncio.run(scenario())


def test_invalid_tts_audio_is_rejected_and_request_is_cancelled() -> None:
    async def scenario() -> None:
        cancelled: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/audio/transcriptions":
                return httpx.Response(200, json={"text": "Hello"})
            if request.url.path == "/v1/audio/speech":
                return httpx.Response(200, content=b"not a wav")
            if request.url.path.endswith("/cancel"):
                cancelled.append(request.url.path)
                return httpx.Response(200)
            raise AssertionError(f"unexpected path {request.url.path}")

        gateway = _gateway(httpx.MockTransport(handler))
        provider = ModelDeckProvider(gateway, pipeline_timeout_seconds=30)
        request = ModelDeckRunRequest.model_validate(
            {
                "mode": "voice",
                "selection_id": "aiden",
                "audio_format": {
                    "encoding": "pcm_s16le",
                    "sample_rate_hz": 16_000,
                    "channels": 1,
                },
            }
        )
        events: list[dict[str, object]] = []

        async def send_json(event: dict[str, object]) -> None:
            events.append(event)

        await provider.run(
            Session(id="test-session"),
            request,
            b"\x00\x10" * 3_200,
            1,
            send_json,
            lambda _: asyncio.sleep(0),
        )

        assert events[-1]["type"] == "error"
        assert events[-1]["code"] == "invalid_output_audio"
        assert len(cancelled) == 1
        await gateway.close()

    asyncio.run(scenario())
