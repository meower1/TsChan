from __future__ import annotations

import httpx
import pytest

from melodify_ts_bot.ts3audiobot_client import TS3AudioBotClient


@pytest.mark.asyncio
async def test_play_url_uses_bot_use_command_path() -> None:
    seen_path: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        transport=httpx.MockTransport(handler),
        auth=("api", "pass"),
    )
    ts3 = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="api",
        password="pass",
        bot_id=0,
        client=client,
    )

    await ts3.play_url("https://example.com/track.mp3")
    assert seen_path is not None
    assert seen_path.startswith("/api/bot/use/0/(/play/")
    assert "https://example.com/track.mp3" in seen_path or "https%3A%2F%2Fexample.com%2Ftrack.mp3" in seen_path


@pytest.mark.asyncio
async def test_song_status_parsing() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Value": {"Title": "Live Track"}})

    client = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        transport=httpx.MockTransport(handler),
        auth=("api", "pass"),
    )
    ts3 = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="api",
        password="pass",
        bot_id=0,
        client=client,
    )

    status = await ts3.get_song_status()
    assert status.is_playing is True
    assert status.title == "Live Track"


@pytest.mark.asyncio
async def test_falls_back_to_anonymous_when_basic_auth_rejected() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            assert request.headers.get("authorization", "").startswith("Basic ")
            return httpx.Response(401, text="unauthorized")
        assert request.headers.get("authorization") is None
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        transport=httpx.MockTransport(handler),
    )
    ts3 = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="api",
        password="pass",
        bot_id=0,
        client=client,
    )

    await ts3.stop()
    assert call_count == 2


@pytest.mark.asyncio
async def test_play_url_accepts_204_no_content_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        transport=httpx.MockTransport(handler),
    )
    ts3 = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="",
        password="",
        bot_id=0,
        client=client,
    )

    response = await ts3.play_url("https://example.com/track.mp3")
    assert response is None


@pytest.mark.asyncio
async def test_skip_uses_next_command() -> None:
    seen_path: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(204)

    client = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        transport=httpx.MockTransport(handler),
    )
    ts3 = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="",
        password="",
        bot_id=0,
        client=client,
    )

    await ts3.skip()
    assert seen_path == "/api/bot/use/0/(/next)"


@pytest.mark.asyncio
async def test_pause_uses_pause_command() -> None:
    seen_path: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(204)

    client = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        transport=httpx.MockTransport(handler),
    )
    ts3 = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="",
        password="",
        bot_id=0,
        client=client,
    )

    await ts3.pause()
    assert seen_path == "/api/bot/use/0/(/pause)"


@pytest.mark.asyncio
async def test_connect_uses_connect_command() -> None:
    seen_path: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(204)

    client = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        transport=httpx.MockTransport(handler),
    )
    ts3 = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="",
        password="",
        bot_id=0,
        client=client,
    )

    await ts3.connect()
    assert seen_path == "/api/bot/use/0/(/connect)"
