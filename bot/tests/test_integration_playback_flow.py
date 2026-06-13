from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from melodify_ts_bot.melodify_client import MelodifyClient
from melodify_ts_bot.queue_manager import PlaybackCoordinator
from melodify_ts_bot.ts3audiobot_client import TS3AudioBotClient


@pytest.mark.asyncio
async def test_search_pick_play_end_to_end() -> None:
    def melodify_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": [
                        {
                            "id": 99,
                            "title": "E2E Song",
                            "artist": "E2E Artist",
                            "duration": 200,
                            "available_qualities": ["320"],
                        }
                    ]
                },
            )
        if request.url.path == "/v1/stream-token":
            return httpx.Response(
                200,
                json={
                    "stream_url": "https://mel.example/v1/stream/token-1",
                    "expires_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/auth/status":
            return httpx.Response(200, json={"logged_in": True})
        return httpx.Response(404)

    ts3_calls: list[str] = []

    def ts3_handler(request: httpx.Request) -> httpx.Response:
        ts3_calls.append(request.url.path)
        if "(/song)" in request.url.path or "%28%2Fsong%29" in request.url.path:
            return httpx.Response(200, json={"Value": {"Title": "E2E Song"}})
        return httpx.Response(200, json={"ok": True})

    melodify_http = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(melodify_handler),
    )
    ts3_http = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        auth=("api", "pass"),
        transport=httpx.MockTransport(ts3_handler),
    )

    melodify = MelodifyClient("https://mel.example", "k", client=melodify_http)
    ts3audiobot = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="api",
        password="pass",
        bot_id=0,
        client=ts3_http,
    )

    coordinator = PlaybackCoordinator(
        melodify=melodify,
        ts3audiobot=ts3audiobot,
        default_quality="320",
        pending_ttl_seconds=90,
        poll_seconds=5,
        minimum_active_users=1,
    )
    await coordinator.update_presence(
        bot_online=True,
        bot_channel_id="1",
        active_human_users=1,
    )

    tracks = await melodify.search_tracks("song")
    await coordinator.add_pending_pick(
        channel_id="1",
        invoker_id="1",
        invoker_name="user",
        query="song",
        tracks=tracks,
    )
    await coordinator.pick_track(
        channel_id="1",
        invoker_id="1",
        invoker_name="user",
        pick_index=1,
    )

    snapshot = await coordinator.state_snapshot()
    assert snapshot["current"] is not None
    assert any("(/play" in call or "%28%2Fplay" in call for call in ts3_calls)


@pytest.mark.asyncio
async def test_stream_token_failure_keeps_queue() -> None:
    def melodify_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": [
                        {
                            "id": 99,
                            "title": "E2E Song",
                            "artist": "E2E Artist",
                            "duration": 200,
                            "available_qualities": ["320"],
                        }
                    ]
                },
            )
        if request.url.path == "/v1/stream-token":
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(404)

    def ts3_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    melodify_http = httpx.AsyncClient(
        base_url="https://mel.example",
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(melodify_handler),
    )
    ts3_http = httpx.AsyncClient(
        base_url="http://ts3ab.local",
        auth=("api", "pass"),
        transport=httpx.MockTransport(ts3_handler),
    )

    melodify = MelodifyClient("https://mel.example", "k", client=melodify_http)
    ts3audiobot = TS3AudioBotClient(
        base_url="http://ts3ab.local",
        username="api",
        password="pass",
        bot_id=0,
        client=ts3_http,
    )

    coordinator = PlaybackCoordinator(
        melodify=melodify,
        ts3audiobot=ts3audiobot,
        default_quality="320",
        pending_ttl_seconds=90,
        poll_seconds=5,
        minimum_active_users=1,
    )
    await coordinator.update_presence(
        bot_online=True,
        bot_channel_id="1",
        active_human_users=1,
    )

    tracks = await melodify.search_tracks("song")
    await coordinator.add_pending_pick(
        channel_id="1",
        invoker_id="1",
        invoker_name="user",
        query="song",
        tracks=tracks,
    )
    await coordinator.pick_track(
        channel_id="1",
        invoker_id="1",
        invoker_name="user",
        pick_index=1,
    )

    snapshot = await coordinator.state_snapshot()
    assert snapshot["current"] is None
    assert len(snapshot["queue"]) == 1
    assert snapshot["last_error"] is not None
