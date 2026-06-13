from __future__ import annotations

import httpx
import pytest

from melodify_ts_bot.errors import MelodifyAuthError, MelodifyNotFoundError
from melodify_ts_bot.melodify_client import MelodifyClient


@pytest.mark.asyncio
async def test_search_tracks_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/search"
        return httpx.Response(
            200,
            json={
                "tracks": [
                    {
                        "id": 42,
                        "title": "Track A",
                        "artist": "Artist",
                        "duration": 123,
                        "available_qualities": ["320", "128"],
                    }
                ]
            },
        )

    client = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(handler),
    )
    api = MelodifyClient("https://mel.example", "k", client=client)

    tracks = await api.search_tracks("hello")
    assert tracks[0].track_id == "42"
    assert tracks[0].title == "Track A"


@pytest.mark.asyncio
async def test_stream_token_auth_failure() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid"})

    client = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(handler),
    )
    api = MelodifyClient("https://mel.example", "k", client=client)

    with pytest.raises(MelodifyAuthError):
        await api.create_stream_token("1", "320")


@pytest.mark.asyncio
async def test_stream_token_not_found() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    client = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(handler),
    )
    api = MelodifyClient("https://mel.example", "k", client=client)

    with pytest.raises(MelodifyNotFoundError):
        await api.create_stream_token("1", "320")


@pytest.mark.asyncio
async def test_stream_token_falls_back_to_legacy_relay_on_missing_endpoint() -> None:
    async def relay(track_id: str, quality: str) -> str:
        assert track_id == "55"
        assert quality == "320"
        return "http://python-orchestrator:8090/internal/stream/fallback-token"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Not Found"})

    client = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(handler),
    )
    api = MelodifyClient(
        "https://mel.example",
        "k",
        client=client,
        legacy_stream_url_factory=relay,
    )

    token = await api.create_stream_token("55", "320")
    assert token.stream_url.endswith("/fallback-token")


@pytest.mark.asyncio
async def test_stream_token_numeric_track_id_is_sent_as_number() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/stream-token"
        payload = request.read().decode("utf-8")
        assert '"track_id":42' in payload
        return httpx.Response(
            200,
            json={
                "stream_url": "https://mel.example/v1/stream/token-1",
                "expires_at": "2030-01-01T00:00:00+00:00",
            },
        )

    client = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(handler),
    )
    api = MelodifyClient("https://mel.example", "k", client=client)

    token = await api.create_stream_token("42", "320")
    assert token.stream_url.endswith("token-1")


@pytest.mark.asyncio
async def test_download_by_track_id_numeric_track_id_is_sent_as_number() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/download/by-track-id"
        payload = request.read().decode("utf-8")
        assert '"track_id":42' in payload
        return httpx.Response(
            200,
            content=b"mp3-bytes",
            headers={"content-type": "audio/mpeg", "content-disposition": "attachment; filename=test.mp3"},
        )

    client = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(handler),
    )
    api = MelodifyClient("https://mel.example", "k", client=client)

    content, content_type, content_disposition = await api.download_by_track_id("42", "320")
    assert content == b"mp3-bytes"
    assert content_type == "audio/mpeg"
    assert content_disposition is not None
