from __future__ import annotations

import asyncio
import base64
import io
import json
import time
import wave
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import httpx

from speechshift.models import ModelDeckRunRequest, ShiftMode
from speechshift.sessions import Session

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBytes = Callable[[bytes], Awaitable[None]]

MODELDECK_MODELS = frozenset(
    {"speechshift-stt", "speechshift-en-fr", "speechshift-en-de", "speechshift-voice"}
)
MODELDECK_VOICES = {
    "ryan": ("Ryan", "Dynamic built-in synthetic male voice"),
    "aiden": ("Aiden", "Sunny built-in synthetic male voice"),
    "vivian": ("Vivian", "Bright built-in synthetic female voice"),
    "serena": ("Serena", "Warm, gentle built-in synthetic female voice"),
}
LANGUAGE_MODELS = {"fr": "speechshift-en-fr", "de": "speechshift-en-de"}
LANGUAGE_LABELS = {"fr": "French", "de": "German"}


class ModelDeckError(RuntimeError):
    def __init__(self, code: str, *, recoverable: bool = True) -> None:
        super().__init__(code)
        self.code = code
        self.recoverable = recoverable


class ModelDeckGateway:
    MAXIMUM_OUTPUT_WAV_BYTES = 2_000_000

    def __init__(
        self,
        base_url: str,
        *,
        stt_timeout_seconds: float,
        translation_timeout_seconds: float,
        tts_timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )
        self._stt_timeout = stt_timeout_seconds
        self._translation_timeout = translation_timeout_seconds
        self._tts_timeout = tts_timeout_seconds

    async def close(self) -> None:
        await self._client.aclose()

    async def ready(self) -> bool:
        try:
            response = await self._client.get("/v1/routes", timeout=0.25)
            response.raise_for_status()
            payload = response.json()
            routes = payload.get("routes") if isinstance(payload, dict) else None
            if not isinstance(routes, list):
                return False
            ready_models = {
                route.get("public_name")
                for route in routes
                if isinstance(route, dict) and route.get("ready") is True
            }
            return MODELDECK_MODELS <= ready_models
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    async def transcribe(self, request_id: str, pcm: bytes, sample_rate: int) -> str:
        payload = {
            "request_id": request_id,
            "model": "speechshift-stt",
            "language": "en",
            "encoding": "pcm_s16le",
            "sample_rate_hz": sample_rate,
            "channels": 1,
            "audio_base64": base64.b64encode(pcm).decode("ascii"),
        }
        response = await self._request(
            "POST", "/v1/audio/transcriptions", json=payload, timeout=self._stt_timeout
        )
        body = _json_object(response)
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ModelDeckError("invalid_transcription_response")
        return text.strip()

    async def translate(self, request_id: str, text: str, target_language: str) -> str:
        model = LANGUAGE_MODELS.get(target_language)
        if model is None:
            raise ModelDeckError("unsupported_language")
        response = await self._request(
            "POST",
            "/v1/translations",
            json={
                "request_id": request_id,
                "model": model,
                "input": text,
                "source_language": "en",
                "target_language": target_language,
            },
            timeout=self._translation_timeout,
        )
        body = _json_object(response)
        output = body.get("output_text")
        if not isinstance(output, str) or not output.strip():
            raise ModelDeckError("invalid_translation_response")
        return output.strip()

    async def synthesise(self, request_id: str, text: str, *, voice: str, language: str) -> tuple[bytes, int]:
        if voice not in MODELDECK_VOICES:
            raise ModelDeckError("unsupported_voice")
        wav = await self._request_audio(
            "/v1/audio/speech",
            json={
                "request_id": request_id,
                "model": "speechshift-voice",
                "input": text,
                "voice": voice,
                "language": language,
                "response_format": "wav",
            },
            timeout=self._tts_timeout,
        )
        try:
            with wave.open(io.BytesIO(wav), "rb") as audio:
                if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                    raise ModelDeckError("invalid_output_audio")
                sample_rate = audio.getframerate()
                if sample_rate != 24_000:
                    raise ModelDeckError("invalid_output_audio")
                pcm = audio.readframes(audio.getnframes())
        except (EOFError, wave.Error) as error:
            raise ModelDeckError("invalid_output_audio") from error
        if not pcm:
            raise ModelDeckError("invalid_output_audio")
        return pcm, sample_rate

    async def cancel(self, request_id: str) -> None:
        try:
            await self._client.post(f"/v1/requests/{request_id}/cancel", timeout=2)
        except httpx.HTTPError:
            return

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as error:
            raise ModelDeckError("modeldeck_timeout") from error
        except httpx.HTTPError as error:
            raise ModelDeckError("modeldeck_unavailable") from error
        if response.is_success:
            return response
        code = "modeldeck_request_failed"
        try:
            payload = response.json()
            error_payload = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error_payload, dict) and isinstance(error_payload.get("code"), str):
                code = error_payload["code"]
        except ValueError:
            pass
        raise ModelDeckError(code, recoverable=response.status_code < 500)

    async def _request_audio(self, path: str, **kwargs: Any) -> bytes:
        try:
            async with self._client.stream("POST", path, **kwargs) as response:
                if not response.is_success:
                    error_content = bytearray()
                    async for chunk in response.aiter_bytes():
                        error_content.extend(chunk)
                        if len(error_content) > 65_536:
                            break
                    code = "modeldeck_request_failed"
                    try:
                        payload = json.loads(error_content)
                        error_payload = payload.get("error") if isinstance(payload, dict) else None
                        if isinstance(error_payload, dict) and isinstance(error_payload.get("code"), str):
                            code = error_payload["code"]
                    except (UnicodeDecodeError, ValueError):
                        pass
                    raise ModelDeckError(
                        code,
                        recoverable=response.status_code < 500,
                    )
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.MAXIMUM_OUTPUT_WAV_BYTES:
                        raise ModelDeckError("output_audio_limit")
                return bytes(content)
        except ModelDeckError:
            raise
        except httpx.TimeoutException as error:
            raise ModelDeckError("modeldeck_timeout") from error
        except httpx.HTTPError as error:
            raise ModelDeckError("modeldeck_unavailable") from error


class ModelDeckProvider:
    OUTPUT_CHUNK_BYTES = 6_400

    def __init__(self, gateway: ModelDeckGateway, *, pipeline_timeout_seconds: float) -> None:
        self._gateway = gateway
        self._pipeline_timeout_seconds = pipeline_timeout_seconds

    async def run(
        self,
        session: Session,
        request: ModelDeckRunRequest,
        input_pcm: bytes,
        input_frames: int,
        send_json: SendJson,
        send_bytes: SendBytes,
    ) -> None:
        generation = session.generation
        started = time.perf_counter()
        active_request_id: str | None = None

        async def emit(event_type: str, **payload: Any) -> None:
            if session.cancelled.is_set() or generation != session.generation:
                raise asyncio.CancelledError
            await send_json(
                {
                    "type": event_type,
                    "sequence": session.next_sequence(),
                    "session_id": session.id,
                    "generation": generation,
                    "modeldeck": True,
                    **payload,
                }
            )

        def set_active_request_id(request_id: str) -> None:
            nonlocal active_request_id
            active_request_id = request_id

        try:
            async with asyncio.timeout(self._pipeline_timeout_seconds):
                await self._run_pipeline(
                    session,
                    request,
                    input_pcm,
                    input_frames,
                    started,
                    generation,
                    emit,
                    send_bytes,
                    set_active_request_id,
                )
        except ModelDeckError as error:
            if active_request_id:
                await asyncio.shield(self._gateway.cancel(active_request_id))
            await emit("error", code=error.code, recoverable=error.recoverable)
        except TimeoutError:
            if active_request_id:
                await asyncio.shield(self._gateway.cancel(active_request_id))
            await emit("error", code="modeldeck_timeout", recoverable=True)
        except asyncio.CancelledError:
            if active_request_id:
                await asyncio.shield(self._gateway.cancel(active_request_id))
            raise

    async def _run_pipeline(
        self,
        session: Session,
        request: ModelDeckRunRequest,
        input_pcm: bytes,
        input_frames: int,
        started: float,
        generation: int,
        emit: Callable[..., Awaitable[None]],
        send_bytes: SendBytes,
        set_active_request_id: Callable[[str], None],
    ) -> None:
        await emit("state", state="recognising", stage="recognised", detail="Recognising locally")
        active_request_id = str(uuid4())
        set_active_request_id(active_request_id)
        transcript = await self._gateway.transcribe(
            active_request_id, input_pcm, request.audio_format.sample_rate_hz
        )
        await emit("transcript_final", text=transcript, stage="recognised")

        output_text = transcript
        output_language = "en"
        voice = request.selection_id if request.mode is ShiftMode.VOICE else "ryan"
        if request.mode is ShiftMode.LANGUAGE:
            output_language = request.selection_id
            active_request_id = str(uuid4())
            set_active_request_id(active_request_id)
            await emit("state", state="translating", stage="translated", detail="Translating locally")
            output_text = await self._gateway.translate(active_request_id, transcript, output_language)
            await emit("translation_final", text=output_text, stage="translated")

        active_request_id = str(uuid4())
        set_active_request_id(active_request_id)
        await emit("state", state="generating", stage="generated", detail="Generating locally")
        output_pcm, sample_rate = await self._gateway.synthesise(
            active_request_id,
            output_text,
            voice=voice,
            language=output_language,
        )
        await emit(
            "audio_start",
            stage="generated",
            label=f"ModelDeck · {MODELDECK_VOICES[voice][0]}",
            audio_format={"encoding": "pcm_s16le", "sample_rate_hz": sample_rate, "channels": 1},
        )
        output_sequence = 1
        for offset in range(0, len(output_pcm), self.OUTPUT_CHUNK_BYTES):
            if session.cancelled.is_set() or generation != session.generation:
                raise asyncio.CancelledError
            await send_bytes(
                output_sequence.to_bytes(4, "little") + output_pcm[offset : offset + self.OUTPUT_CHUNK_BYTES]
            )
            output_sequence += 1
            await asyncio.sleep(0)
        await emit("audio_end", stage="generated", frames=output_sequence - 1)
        await emit(
            "metrics",
            input_audio_ms=round(len(input_pcm) / (request.audio_format.sample_rate_hz * 2) * 1_000),
            input_frames=input_frames,
            first_audio_latency_ms=round((time.perf_counter() - started) * 1_000),
        )
        await emit("complete", state="complete")


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as error:
        raise ModelDeckError("invalid_modeldeck_response") from error
    if not isinstance(payload, dict):
        raise ModelDeckError("invalid_modeldeck_response")
    return payload
