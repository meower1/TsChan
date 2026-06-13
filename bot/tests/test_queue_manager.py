from __future__ import annotations

from datetime import datetime, timezone

import pytest

from melodify_ts_bot.errors import MelodifyAuthError
from melodify_ts_bot.models import SearchTrack, StreamTokenResult
from melodify_ts_bot.queue_manager import PlaybackCoordinator


class FakeMelodify:
    def __init__(self, *, fail_auth: bool = False) -> None:
        self.fail_auth = fail_auth

    async def create_stream_token(self, track_id: str, quality: str) -> StreamTokenResult:
        if self.fail_auth:
            raise MelodifyAuthError("not logged in")
        return StreamTokenResult(
            stream_url=f"https://stream.local/{track_id}.mp3",
            expires_at=datetime.now(timezone.utc),
        )

    async def search_tracks(self, query: str, *, limit: int = 5) -> list[SearchTrack]:
        return [
            SearchTrack(
                track_id="1",
                title="Song",
                artist="Artist",
                duration=120,
                available_qualities=["320"],
            )
        ]


class FakeTS3AudioBot:
    def __init__(self) -> None:
        self.played_urls: list[str] = []
        self.playing = False

    async def play_url(self, url: str) -> None:
        self.played_urls.append(url)
        self.playing = True

    async def get_song_status(self):
        class Status:
            def __init__(self, is_playing: bool) -> None:
                self.is_playing = is_playing

        return Status(self.playing)

    async def skip(self) -> None:
        self.playing = False

    async def stop(self) -> None:
        self.playing = False

    async def pause(self) -> None:
        self.playing = not self.playing


@pytest.mark.asyncio
async def test_pick_enqueues_and_starts_playback() -> None:
    melodify = FakeMelodify()
    ts3 = FakeTS3AudioBot()
    coordinator = PlaybackCoordinator(
        melodify=melodify,
        ts3audiobot=ts3,
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

    tracks = await melodify.search_tracks("q")
    await coordinator.add_pending_pick(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        query="q",
        tracks=tracks,
    )

    queued = await coordinator.pick_track(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        pick_index=1,
    )

    assert queued.track_id == "1"
    assert ts3.played_urls == ["https://stream.local/1.mp3"]

    snapshot = await coordinator.state_snapshot()
    assert snapshot["current"] is not None
    assert snapshot["queue"] == []


@pytest.mark.asyncio
async def test_auth_failure_keeps_queue_item() -> None:
    melodify = FakeMelodify(fail_auth=True)
    ts3 = FakeTS3AudioBot()
    coordinator = PlaybackCoordinator(
        melodify=melodify,
        ts3audiobot=ts3,
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

    tracks = await FakeMelodify().search_tracks("q")
    await coordinator.add_pending_pick(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        query="q",
        tracks=tracks,
    )
    await coordinator.pick_track(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        pick_index=1,
    )

    snapshot = await coordinator.state_snapshot()
    assert snapshot["current"] is None
    assert len(snapshot["queue"]) == 1
    assert "auth/session invalid" in (snapshot["last_error"] or "")


@pytest.mark.asyncio
async def test_loop_requeues_current_track_when_finished() -> None:
    melodify = FakeMelodify()
    ts3 = FakeTS3AudioBot()
    coordinator = PlaybackCoordinator(
        melodify=melodify,
        ts3audiobot=ts3,
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

    tracks = await melodify.search_tracks("q")
    await coordinator.add_pending_pick(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        query="q",
        tracks=tracks,
    )
    await coordinator.pick_track(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        pick_index=1,
    )

    await coordinator.configure_loop_for_current(
        requested_by="user",
        duration_seconds=None,
    )

    ts3.playing = False
    await coordinator.tick()

    snapshot = await coordinator.state_snapshot()
    assert snapshot["current"] is None
    assert len(snapshot["queue"]) == 1
    assert snapshot["loop_state"]["enabled"] is True


@pytest.mark.asyncio
async def test_presence_pause_and_resume() -> None:
    melodify = FakeMelodify()
    ts3 = FakeTS3AudioBot()
    coordinator = PlaybackCoordinator(
        melodify=melodify,
        ts3audiobot=ts3,
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

    tracks = await melodify.search_tracks("q")
    await coordinator.add_pending_pick(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        query="q",
        tracks=tracks,
    )
    await coordinator.pick_track(
        channel_id="1",
        invoker_id="2",
        invoker_name="user",
        pick_index=1,
    )

    await coordinator.update_presence(
        bot_online=True,
        bot_channel_id="1",
        active_human_users=0,
    )
    await coordinator.tick()
    paused_snapshot = await coordinator.state_snapshot()
    assert paused_snapshot["presence_state"]["paused_for_empty_channel"] is True

    await coordinator.update_presence(
        bot_online=True,
        bot_channel_id="1",
        active_human_users=1,
    )
    await coordinator.tick()
    resumed_snapshot = await coordinator.state_snapshot()
    assert resumed_snapshot["presence_state"]["paused_for_empty_channel"] is False
