from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest

from melodify_ts_bot.errors import MelodifyAuthError
from melodify_ts_bot.models import QueuedTrack
from melodify_ts_bot.ops_api import create_ops_app
from melodify_ts_bot.stream_proxy import StreamRelayStore


@dataclass
class _FakeSongStatusClient:
    async def readiness(self) -> bool:
        return True


class _FakeMelodify:
    async def health(self) -> bool:
        return True

    async def search_tracks(self, query: str, *, limit: int = 5) -> list:
        return []

    async def download_by_track_id(self, track_id: str, quality: str) -> tuple[bytes, str | None, str | None]:
        assert track_id == "9001"
        assert quality == "320"
        return b"mp3-data", "audio/mpeg", "attachment; filename=test.mp3"


class _FakeCoordinator:
    def __init__(self, *, fail_smoke_auth: bool = False) -> None:
        self._fail_smoke_auth = fail_smoke_auth

    async def state_snapshot(self) -> dict:
        return {"ts_connected": True, "last_error": None, "queue": [], "current": None}

    async def smoke_enqueue_first_result(self, query: str) -> QueuedTrack:
        if self._fail_smoke_auth:
            raise MelodifyAuthError("bad api key")
        return QueuedTrack(
            track_id="1",
            title=f"track for {query}",
            artist="artist",
            duration=120,
            quality="320",
            requested_by="smoke",
            requested_by_id="smoke",
            requested_channel_id="smoke",
            source_query=query,
        )


@pytest.mark.asyncio
async def test_internal_stream_single_use() -> None:
    relay = StreamRelayStore(ttl_seconds=60)
    token, _ = await relay.issue(track_id="9001", quality="320")
    app = create_ops_app(
        coordinator=_FakeCoordinator(),
        melodify=_FakeMelodify(),
        ts3audiobot=_FakeSongStatusClient(),
        debug_token="dbg",
        smoke_default_query="q",
        stream_relay=relay,
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    first = await client.get(f"/internal/stream/{token}")
    assert first.status_code == 200
    assert first.content == b"mp3-data"

    second = await client.get(f"/internal/stream/{token}")
    assert second.status_code == 410

    await client.aclose()


@pytest.mark.asyncio
async def test_debug_smoke_play_maps_auth_errors_to_502() -> None:
    app = create_ops_app(
        coordinator=_FakeCoordinator(fail_smoke_auth=True),
        melodify=_FakeMelodify(),
        ts3audiobot=_FakeSongStatusClient(),
        debug_token="dbg",
        smoke_default_query="q",
        stream_relay=None,
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    response = await client.post(
        "/debug/smoke-play",
        headers={"Authorization": "Bearer dbg"},
        json={"query": "test"},
    )
    assert response.status_code == 502
    assert "Melodify auth error" in response.text

    await client.aclose()


class _FakeMelodifySearchFails(_FakeMelodify):
    async def search_tracks(self, query: str, *, limit: int = 5) -> list:
        raise MelodifyAuthError("inactive_session")


@pytest.mark.asyncio
async def test_health_ready_is_503_when_melodify_search_fails() -> None:
    app = create_ops_app(
        coordinator=_FakeCoordinator(),
        melodify=_FakeMelodifySearchFails(),
        ts3audiobot=_FakeSongStatusClient(),
        debug_token="dbg",
        smoke_default_query="q",
        stream_relay=None,
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    response = await client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["ready"] is False
    assert payload["checks"]["melodify_health"] is True
    assert payload["checks"]["melodify_search"] is False

    await client.aclose()
