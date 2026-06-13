from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable

import httpx

from .errors import MelodifyAuthError, MelodifyError, MelodifyNotFoundError
from .models import SearchTrack, StreamTokenResult


class MelodifyClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 30.0,
        legacy_stream_url_factory: Callable[[str, str], Awaitable[str]] | None = None,
        force_legacy_stream_url: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owned_client = client is None
        self._legacy_stream_url_factory = legacy_stream_url_factory
        self._force_legacy_stream_url = force_legacy_stream_url
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"X-API-Key": api_key},
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=5,
                keepalive_expiry=30,
            ),
        )

    async def close(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def health(self) -> bool:
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def auth_status(self) -> dict[str, Any]:
        response = await self._client.get("/v1/auth/status")
        if response.status_code == 401:
            raise MelodifyAuthError("Melodify API key is invalid")
        if response.status_code >= 400:
            raise MelodifyError(
                f"Melodify auth status failed: {response.status_code} {response.text[:200]}"
            )
        return response.json()

    async def search_tracks(self, query: str, *, limit: int = 5) -> list[SearchTrack]:
        response = await self._client.get("/v1/search", params={"q": query, "offset": 0})
        if response.status_code == 401:
            raise MelodifyAuthError("Melodify rejected credentials")
        if response.status_code >= 400:
            raise MelodifyError(
                f"Melodify search failed: {response.status_code} {response.text[:200]}"
            )

        data = response.json()
        tracks: list[SearchTrack] = []
        for raw in data.get("tracks", [])[:limit]:
            title = raw.get("title") or f"track-{raw.get('id', 'unknown')}"
            tracks.append(
                SearchTrack(
                    track_id=str(raw.get("id")),
                    title=str(title),
                    artist=raw.get("artist"),
                    duration=raw.get("duration"),
                    available_qualities=[
                        str(quality)
                        for quality in raw.get("available_qualities", [])
                        if quality is not None
                    ],
                )
            )

        return tracks

    async def create_stream_token(
        self,
        track_id: str,
        quality: str,
    ) -> StreamTokenResult:
        if self._force_legacy_stream_url and self._legacy_stream_url_factory is not None:
            return StreamTokenResult(
                stream_url=await self._legacy_stream_url_factory(track_id, quality),
                expires_at=None,
            )

        payload_track_id: str | int = track_id
        if track_id.isdigit():
            payload_track_id = int(track_id)

        response = await self._client.post(
            "/v1/stream-token",
            json={"track_id": payload_track_id, "quality": quality},
        )

        if response.status_code == 401:
            raise MelodifyAuthError("Melodify auth/session is invalid")
        if response.status_code == 404:
            if (
                self._legacy_stream_url_factory is not None
                and self._is_missing_stream_token_endpoint(response)
            ):
                return StreamTokenResult(
                    stream_url=await self._legacy_stream_url_factory(track_id, quality),
                    expires_at=None,
                )
            raise MelodifyNotFoundError(
                "Track was not in backend cache. Run .play again before .pick."
            )
        if response.status_code >= 400:
            raise MelodifyError(
                f"Melodify stream-token failed: {response.status_code} {response.text[:200]}"
            )

        payload = response.json()
        expires_at_raw = payload.get("expires_at")
        expires_at: datetime | None = None
        if isinstance(expires_at_raw, str):
            try:
                expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
            except ValueError:
                expires_at = None

        return StreamTokenResult(
            stream_url=str(payload["stream_url"]),
            expires_at=expires_at,
            title=payload.get("title"),
            artist=payload.get("artist"),
            duration=payload.get("duration"),
        )

    async def download_by_track_id(self, track_id: str, quality: str) -> tuple[bytes, str | None, str | None]:
        payload_track_id: str | int = track_id
        if track_id.isdigit():
            payload_track_id = int(track_id)

        response = await self._client.post(
            "/v1/download/by-track-id",
            json={"track_id": payload_track_id, "quality": quality},
        )

        if response.status_code == 401:
            raise MelodifyAuthError("Melodify auth/session is invalid")
        if response.status_code >= 400:
            raise MelodifyError(
                f"Melodify download failed: {response.status_code} {response.text[:200]}"
            )

        return (
            response.content,
            response.headers.get("content-type"),
            response.headers.get("content-disposition"),
        )

    @staticmethod
    def _is_missing_stream_token_endpoint(response: httpx.Response) -> bool:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail.strip().lower() == "not found"
        return False
