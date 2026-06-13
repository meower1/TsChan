from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .errors import TS3AudioBotError


@dataclass(frozen=True)
class PlayerStatus:
    is_playing: bool
    title: str | None = None
    raw: Any = None


class TS3AudioBotClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        bot_id: int = 0,
        *,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_id = str(bot_id)
        username = username.strip()
        password = password.strip()
        self._auth: tuple[str, str] | None = (username, password) if username and password else None
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30,
            ),
        )

    async def close(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def readiness(self) -> bool:
        try:
            response = await self._request_with_optional_auth("/openapi/index.html")
            return response.status_code < 500
        except Exception:
            return False

    def _bot_command_path(self, command: str, argument: str | None = None) -> str:
        if argument is None:
            return f"/api/bot/use/{self._bot_id}/(/{command})"
        encoded_arg = quote(argument, safe="")
        return f"/api/bot/use/{self._bot_id}/(/{command}/{encoded_arg})"

    async def _request_with_optional_auth(self, path: str) -> httpx.Response:
        response = await self._client.get(path, auth=self._auth)
        if response.status_code == 401 and self._auth is not None:
            response = await self._client.get(path)
        return response

    async def _api_get(self, path: str) -> Any:
        response = await self._request_with_optional_auth(path)
        if response.status_code >= 400:
            raise TS3AudioBotError(
                f"TS3AudioBot call failed: {response.status_code} {response.text[:200]}"
            )
        if response.status_code == 204 or not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if "json" in content_type.lower():
            return response.json()

        text = response.text.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return response.json()
            except ValueError:
                return text
        return text

    async def play_url(self, url: str) -> Any:
        path = self._bot_command_path("play", url)
        return await self._api_get(path)

    async def skip(self) -> Any:
        path = self._bot_command_path("next")
        return await self._api_get(path)

    async def stop(self) -> Any:
        path = self._bot_command_path("stop")
        return await self._api_get(path)

    async def pause(self) -> Any:
        path = self._bot_command_path("pause")
        return await self._api_get(path)

    async def connect(self) -> Any:
        path = self._bot_command_path("connect")
        return await self._api_get(path)

    async def get_song_status(self) -> PlayerStatus:
        path = self._bot_command_path("song")
        try:
            raw = await self._api_get(path)
        except TS3AudioBotError as exc:
            if "There is nothing on right now" in str(exc):
                return PlayerStatus(is_playing=False, title=None, raw=None)
            raise
        payload = self._unwrap_value(raw)

        title = None
        is_playing = False
        if isinstance(payload, dict):
            for key in ("Title", "title", "Name", "name"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break
            is_playing = bool(title) or bool(payload)
        elif isinstance(payload, str):
            title = payload.strip() or None
            is_playing = bool(title)
        elif payload is not None:
            is_playing = True

        return PlayerStatus(is_playing=is_playing, title=title, raw=raw)

    @staticmethod
    def _unwrap_value(raw: Any) -> Any:
        if isinstance(raw, dict) and "Value" in raw:
            return raw["Value"]
        if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict):
            only = raw[0]
            if "Value" in only:
                return only["Value"]
        return raw
