"""Authenticated transport for the native Hermes serve API.

PartsOps talks to Hermes only through this boundary. The browser never sees the
Hermes API key and no provider-specific Python modules are imported here.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from settings import settings


class HermesTransportError(RuntimeError):
    def __init__(self, message: str, *, code: str = "HERMES_UNAVAILABLE", status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


def is_strong_api_key(value: Optional[str]) -> bool:
    if not value or len(value) < 16:
        return False
    return value not in {"partsops-hermes-secret-key", "change-me", "replace-me"}


class HermesTransport:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = (base_url or settings.HERMES_API_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.HERMES_API_KEY
        self.http_transport = transport
        self.timeout = httpx.Timeout(
            connect=3.0,
            read=float(settings.COPILOT_TIMEOUT_SECONDS),
            write=5.0,
            pool=3.0,
        )

    def _headers(self) -> Dict[str, str]:
        if not is_strong_api_key(self.api_key):
            raise HermesTransportError(
                "Hermes API key is missing or weak",
                code="HERMES_KEY_NOT_CONFIGURED",
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "X-Hermes-Client": "partsops-copilot",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    @staticmethod
    def _raise_for_response(response: httpx.Response) -> None:
        if response.is_success:
            return
        if response.status_code in {401, 403}:
            raise HermesTransportError("Hermes отклонил авторизацию", code="HERMES_AUTH_FAILED", status_code=response.status_code)
        if response.status_code == 404:
            raise HermesTransportError("Нативный Hermes endpoint не найден", code="HERMES_CONTRACT_MISMATCH", status_code=404)
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise HermesTransportError("Hermes временно перегружен или недоступен", code="HERMES_UPSTREAM_RETRYABLE", status_code=response.status_code, retryable=True)
        raise HermesTransportError("Hermes отклонил запрос", code="HERMES_UPSTREAM_REJECTED", status_code=response.status_code)

    async def capabilities(self) -> Dict[str, Any]:
        headers = self._headers()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.http_transport) as client:
                response = await client.get(self._url("/v1/capabilities"), headers=headers)
            self._raise_for_response(response)
            return response.json()
        except HermesTransportError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise HermesTransportError("Hermes не ответил на проверку capabilities", code="HERMES_TIMEOUT", retryable=True) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HermesTransportError("Hermes вернул некорректный capabilities response", code="HERMES_INVALID_RESPONSE") from exc

    async def start_run(
        self,
        *,
        message: str,
        instructions: str,
        conversation_history: List[Dict[str, str]],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        headers = self._headers()
        body: Dict[str, Any] = {
            "input": message,
            "instructions": instructions,
            "conversation_history": conversation_history,
        }
        if session_id:
            body["session_id"] = session_id
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.http_transport) as client:
                response = await client.post(self._url("/v1/runs"), headers=headers, json=body)
            self._raise_for_response(response)
            payload = response.json()
            if not payload.get("run_id"):
                raise HermesTransportError("Hermes start response не содержит run_id", code="HERMES_INVALID_RESPONSE")
            return payload
        except HermesTransportError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise HermesTransportError("Hermes не принял запуск run", code="HERMES_START_TIMEOUT", retryable=True) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HermesTransportError("Hermes вернул некорректный start response", code="HERMES_INVALID_RESPONSE") from exc

    async def stream_run(self, hermes_run_id: str) -> AsyncIterator[Dict[str, Any]]:
        headers = {**self._headers(), "Accept": "text/event-stream", "Cache-Control": "no-cache"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.http_transport) as client:
                async with client.stream("GET", self._url(f"/v1/runs/{hermes_run_id}/events"), headers=headers) as response:
                    self._raise_for_response(response)
                    frame: List[str] = []
                    async for line in response.aiter_lines():
                        if line == "":
                            event = self._decode_frame(frame)
                            frame = []
                            if event is not None:
                                yield event
                            continue
                        if line.startswith("data:"):
                            frame.append(line[5:].strip())
                    event = self._decode_frame(frame)
                    if event is not None:
                        yield event
        except HermesTransportError:
            raise
        except asyncio.CancelledError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise HermesTransportError("Поток Hermes прерван по timeout или network error", code="HERMES_STREAM_TIMEOUT", retryable=True) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HermesTransportError("Hermes вернул некорректный event stream", code="HERMES_INVALID_STREAM") from exc

    async def stop_run(self, hermes_run_id: str) -> Dict[str, Any]:
        headers = self._headers()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0), transport=self.http_transport) as client:
                response = await client.post(self._url(f"/v1/runs/{hermes_run_id}/stop"), headers=headers)
            self._raise_for_response(response)
            return response.json() if response.content else {"status": "stopped"}
        except HermesTransportError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise HermesTransportError("Hermes stop не подтвердил остановку", code="HERMES_STOP_TIMEOUT", retryable=True) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HermesTransportError("Hermes вернул некорректный stop response", code="HERMES_INVALID_RESPONSE") from exc

    @staticmethod
    def _decode_frame(lines: List[str]) -> Optional[Dict[str, Any]]:
        if not lines:
            return None
        payload = "\n".join(lines)
        if payload == "[DONE]":
            return None
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
