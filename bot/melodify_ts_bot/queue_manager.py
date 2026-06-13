from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .errors import MelodifyAuthError, MelodifyError, MelodifyNotFoundError, TS3AudioBotError
from .melodify_client import MelodifyClient
from .models import CurrentPlayback, PendingPick, QueuedTrack, SearchTrack, utcnow
from .ts3audiobot_client import TS3AudioBotClient

LOGGER = logging.getLogger(__name__)
_MAX_PENDING_PICKS = 100


@dataclass(slots=True)
class LoopConfig:
    mode: str = "off"  # off | inf | timed
    track_id: str | None = None
    requested_by: str | None = None
    enabled_at: datetime | None = None
    until: datetime | None = None

    def is_enabled(self, now: datetime | None = None) -> bool:
        if self.mode == "off" or not self.track_id:
            return False
        if self.mode == "timed" and self.until is not None:
            return (now or utcnow()) < self.until
        return True


@dataclass(slots=True)
class PendingSummon:
    channel_id: str
    requested_by_id: str
    requested_by_name: str
    requested_at: datetime


class PlaybackCoordinator:
    def __init__(
        self,
        melodify: MelodifyClient,
        ts3audiobot: TS3AudioBotClient,
        *,
        default_quality: str,
        pending_ttl_seconds: int,
        poll_seconds: float,
        minimum_active_users: int,
    ) -> None:
        self._melodify = melodify
        self._ts3audiobot = ts3audiobot
        self._default_quality = default_quality
        self._pending_ttl_seconds = pending_ttl_seconds
        self._poll_seconds = poll_seconds
        self._minimum_active_users = max(minimum_active_users, 1)

        self._queue: deque[QueuedTrack] = deque()
        self._history: deque[QueuedTrack] = deque(maxlen=20)
        self._pending: dict[tuple[str, str], PendingPick] = {}
        self._current: CurrentPlayback | None = None

        self._loop = LoopConfig()
        self._pending_summon: PendingSummon | None = None

        self._lock = asyncio.Lock()
        self._worker_task: asyncio.Task[None] | None = None
        self._stopping = False

        self._last_error: str | None = None
        self._next_retry_at: datetime | None = None
        self._is_ts_connected = False

        self._bot_online = False
        self._bot_channel_id: str | None = None
        self._active_human_users = 0
        self._paused_for_empty_channel = False

    async def start(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return
        self._stopping = False
        self._worker_task = asyncio.create_task(self._worker_loop(), name="playback-worker")

    async def stop(self) -> None:
        self._stopping = True
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def set_ts_connected(self, connected: bool) -> None:
        self._is_ts_connected = connected

    async def update_presence(
        self,
        *,
        bot_online: bool,
        bot_channel_id: str | None,
        active_human_users: int,
    ) -> None:
        async with self._lock:
            self._bot_online = bot_online
            self._bot_channel_id = bot_channel_id
            self._active_human_users = max(active_human_users, 0)

    async def configure_loop_for_current(
        self,
        *,
        requested_by: str,
        duration_seconds: int | None,
    ) -> dict[str, Any]:
        async with self._lock:
            if self._current is None:
                raise ValueError("No active track to loop.")

            now = utcnow()
            until = now + timedelta(seconds=duration_seconds) if duration_seconds is not None else None
            self._loop = LoopConfig(
                mode="timed" if duration_seconds is not None else "inf",
                track_id=self._current.track.track_id,
                requested_by=requested_by,
                enabled_at=now,
                until=until,
            )
            return self._loop_state_payload_locked(now)

    async def disable_loop(self) -> None:
        async with self._lock:
            self._loop = LoopConfig()

    async def set_pending_summon(
        self,
        *,
        channel_id: str,
        requested_by_id: str,
        requested_by_name: str,
    ) -> None:
        async with self._lock:
            self._pending_summon = PendingSummon(
                channel_id=channel_id,
                requested_by_id=requested_by_id,
                requested_by_name=requested_by_name,
                requested_at=utcnow(),
            )

    async def clear_pending_summon(self) -> None:
        async with self._lock:
            self._pending_summon = None

    async def pending_summon_snapshot(self) -> dict[str, Any] | None:
        async with self._lock:
            if self._pending_summon is None:
                return None
            return {
                "channel_id": self._pending_summon.channel_id,
                "requested_by_id": self._pending_summon.requested_by_id,
                "requested_by_name": self._pending_summon.requested_by_name,
                "requested_at": self._pending_summon.requested_at.isoformat(),
            }

    async def _worker_loop(self) -> None:
        while not self._stopping:
            loop_start = asyncio.get_event_loop().time()
            try:
                await asyncio.wait_for(
                    self.tick(),
                    timeout=max(self._poll_seconds * 4, 10.0),
                )
            except asyncio.TimeoutError:
                LOGGER.warning("playback tick timed out")
            except Exception:
                LOGGER.exception("playback tick crashed")
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_time = max(0.0, self._poll_seconds - elapsed)
            await asyncio.sleep(sleep_time)

    async def tick(self) -> None:
        async with self._lock:
            self._cleanup_expired_pending_locked()
            self._cleanup_expired_loop_locked()

            if self._next_retry_at and utcnow() < self._next_retry_at:
                return

            if not self._can_play_locked():
                await self._pause_for_empty_room_locked()
                return

            await self._resume_from_empty_room_locked()

            if self._current is not None:
                await self._tick_current_locked()
                return

            if not self._queue:
                return

            await self._start_next_locked()

    async def _tick_current_locked(self) -> None:
        assert self._current is not None
        if self._paused_for_empty_channel:
            return

        try:
            status = await self._ts3audiobot.get_song_status()
        except TS3AudioBotError as exc:
            self._set_retry_locked(f"TS3AudioBot status error: {exc}")
            return

        if status.is_playing:
            return

        finished = self._current.track
        loop_requeued = self._maybe_requeue_looped_track_locked(finished)

        self._history.append(finished)
        self._current = None
        self._last_error = None
        LOGGER.info(
            "track finished",
            extra={
                "event": "track_finished",
                "track_id": finished.track_id,
                "queue_len": len(self._queue),
                "decision": "finished",
                "reason": "ended",
                "loop_requeued": loop_requeued,
            },
        )

    def _maybe_requeue_looped_track_locked(self, track: QueuedTrack) -> bool:
        now = utcnow()
        if not self._loop.is_enabled(now):
            return False
        if self._loop.track_id != track.track_id:
            return False

        looped = QueuedTrack(
            track_id=track.track_id,
            title=track.title,
            artist=track.artist,
            duration=track.duration,
            quality=track.quality,
            requested_by=track.requested_by,
            requested_by_id=track.requested_by_id,
            requested_channel_id=track.requested_channel_id,
            source_query=track.source_query,
        )
        self._queue.appendleft(looped)
        return True

    async def _start_next_locked(self) -> None:
        track = self._queue[0]
        try:
            token_result = await self._melodify.create_stream_token(
                track_id=track.track_id,
                quality=track.quality,
            )
        except MelodifyAuthError as exc:
            self._set_retry_locked(
                f"Melodify auth/session invalid: {exc}",
                retry_seconds=20,
            )
            return
        except (MelodifyNotFoundError, MelodifyError) as exc:
            self._set_retry_locked(f"Melodify stream token error: {exc}", retry_seconds=10)
            return

        try:
            await self._ts3audiobot.play_url(token_result.stream_url)
        except TS3AudioBotError as exc:
            self._set_retry_locked(f"TS3AudioBot play error: {exc}", retry_seconds=5)
            return

        started = self._queue.popleft()
        self._current = CurrentPlayback(
            track=started,
            stream_url=token_result.stream_url,
            stream_expires_at=token_result.expires_at,
        )
        self._last_error = None
        self._next_retry_at = None

        LOGGER.info(
            "track started",
            extra={"event": "track_started", "track_id": started.track_id, "queue_len": len(self._queue)},
        )

    async def _pause_for_empty_room_locked(self) -> None:
        if self._current is None:
            return
        if self._paused_for_empty_channel:
            return

        try:
            await self._ts3audiobot.pause()
            self._paused_for_empty_channel = True
            LOGGER.info(
                "playback paused due to empty channel",
                extra={
                    "event": "presence_pause",
                    "queue_len": len(self._queue),
                    "reason": "empty_channel",
                },
            )
        except TS3AudioBotError as exc:
            self._set_retry_locked(f"TS3AudioBot pause error: {exc}", retry_seconds=5)

    async def _resume_from_empty_room_locked(self) -> None:
        if not self._paused_for_empty_channel:
            return
        if self._current is None:
            self._paused_for_empty_channel = False
            return

        try:
            await self._ts3audiobot.pause()
            self._paused_for_empty_channel = False
            LOGGER.info(
                "playback resumed after users returned",
                extra={
                    "event": "presence_resume",
                    "queue_len": len(self._queue),
                    "reason": "users_returned",
                },
            )
        except TS3AudioBotError as exc:
            self._set_retry_locked(f"TS3AudioBot resume error: {exc}", retry_seconds=5)

    def _can_play_locked(self) -> bool:
        return (
            self._bot_online
            and self._bot_channel_id is not None
            and self._active_human_users >= self._minimum_active_users
        )

    def _set_retry_locked(self, message: str, retry_seconds: int = 5) -> None:
        self._last_error = message
        self._next_retry_at = utcnow() + timedelta(seconds=retry_seconds)
        LOGGER.warning(message)

    async def add_pending_pick(
        self,
        *,
        channel_id: str,
        invoker_id: str,
        invoker_name: str,
        query: str,
        tracks: list[SearchTrack],
    ) -> PendingPick:
        now = utcnow()
        pending = PendingPick(
            channel_id=channel_id,
            invoker_id=invoker_id,
            invoker_name=invoker_name,
            query=query,
            tracks=tracks,
            created_at=now,
            expires_at=now + timedelta(seconds=self._pending_ttl_seconds),
        )
        async with self._lock:
            # Evict oldest entries if we've hit the hard cap
            while len(self._pending) >= _MAX_PENDING_PICKS:
                oldest_key = next(iter(self._pending))
                del self._pending[oldest_key]
            self._pending[(channel_id, invoker_id)] = pending
        return pending

    async def pick_track(
        self,
        *,
        channel_id: str,
        invoker_id: str,
        invoker_name: str,
        pick_index: int,
    ) -> QueuedTrack:
        async with self._lock:
            pending = self._pending.get((channel_id, invoker_id))
            if pending is None:
                raise ValueError("No pending pick for this user/channel. Run .play first.")
            if pending.is_expired():
                del self._pending[(channel_id, invoker_id)]
                raise ValueError("Your pending results expired. Run .play again.")

            if pick_index < 1 or pick_index > len(pending.tracks):
                raise ValueError(f"Pick must be between 1 and {len(pending.tracks)}")

            choice = pending.tracks[pick_index - 1]
            queued = QueuedTrack(
                track_id=choice.track_id,
                title=choice.title,
                artist=choice.artist,
                duration=choice.duration,
                quality=self._best_quality(choice.available_qualities),
                requested_by=invoker_name,
                requested_by_id=invoker_id,
                requested_channel_id=channel_id,
                source_query=pending.query,
            )
            self._queue.append(queued)
            del self._pending[(channel_id, invoker_id)]

            LOGGER.info(
                "track queued",
                extra={"event": "track_queued", "track_id": queued.track_id, "queue_len": len(self._queue)},
            )

        await self.tick()
        return queued

    def _best_quality(self, available: list[str]) -> str:
        if not available:
            return self._default_quality
        if self._default_quality in available:
            return self._default_quality
        return available[0]

    async def skip_current(self) -> bool:
        async with self._lock:
            current_track_id = self._current.track.track_id if self._current else None
            had_current = self._current is not None
        if not had_current:
            return False

        await self._ts3audiobot.skip()
        async with self._lock:
            self._current = None
            self._paused_for_empty_channel = False
            if self._loop.track_id == current_track_id:
                self._loop = LoopConfig()
        await self.tick()
        return True

    async def stop_all(self) -> None:
        try:
            await self._ts3audiobot.stop()
        except TS3AudioBotError:
            LOGGER.exception("stop command failed")

        async with self._lock:
            self._queue.clear()
            self._current = None
            self._next_retry_at = None
            self._paused_for_empty_channel = False
            self._loop = LoopConfig()

    async def smoke_enqueue_first_result(self, query: str) -> QueuedTrack:
        tracks = await self._melodify.search_tracks(query, limit=1)
        if not tracks:
            raise ValueError("No track returned from melodify search")
        first = tracks[0]
        queued = QueuedTrack(
            track_id=first.track_id,
            title=first.title,
            artist=first.artist,
            duration=first.duration,
            quality=self._best_quality(first.available_qualities),
            requested_by="smoke",
            requested_by_id="smoke",
            requested_channel_id="smoke",
            source_query=query,
        )
        async with self._lock:
            self._queue.append(queued)

        await self.tick()
        return queued

    async def state_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            now = utcnow()
            self._cleanup_expired_pending_locked()
            queue_payload = [self._queued_track_to_dict(track) for track in self._queue]
            pending_payload: list[dict[str, Any]] = []
            for key, pending in self._pending.items():
                if pending.is_expired(now):
                    continue
                pending_payload.append(
                    {
                        "key": {"channel_id": key[0], "invoker_id": key[1]},
                        "query": pending.query,
                        "invoker_name": pending.invoker_name,
                        "expires_at": pending.expires_at.isoformat(),
                        "tracks": [asdict(track) for track in pending.tracks],
                    }
                )

            current_payload = None
            if self._current:
                current_payload = {
                    "track": self._queued_track_to_dict(self._current.track),
                    "started_at": self._current.started_at.isoformat(),
                    "stream_expires_at": self._current.stream_expires_at.isoformat()
                    if self._current.stream_expires_at
                    else None,
                }

            summon_payload = None
            if self._pending_summon:
                summon_payload = {
                    "channel_id": self._pending_summon.channel_id,
                    "requested_by_id": self._pending_summon.requested_by_id,
                    "requested_by_name": self._pending_summon.requested_by_name,
                    "requested_at": self._pending_summon.requested_at.isoformat(),
                }

            return {
                "ts_connected": self._is_ts_connected,
                "current": current_payload,
                "queue": queue_payload,
                "pending_picks": pending_payload,
                "history": [self._queued_track_to_dict(track) for track in self._history],
                "last_error": self._last_error,
                "next_retry_at": self._next_retry_at.isoformat() if self._next_retry_at else None,
                "loop_state": self._loop_state_payload_locked(now),
                "presence_state": {
                    "bot_online": self._bot_online,
                    "bot_channel_id": self._bot_channel_id,
                    "active_human_users": self._active_human_users,
                    "minimum_active_users": self._minimum_active_users,
                    "paused_for_empty_channel": self._paused_for_empty_channel,
                },
                "summon_state": {
                    "pending": summon_payload,
                },
            }

    def _loop_state_payload_locked(self, now: datetime) -> dict[str, Any]:
        enabled = self._loop.is_enabled(now)
        remaining_seconds: int | None = None
        if self._loop.mode == "timed" and self._loop.until is not None:
            remaining_seconds = max(0, int((self._loop.until - now).total_seconds()))

        return {
            "enabled": enabled,
            "mode": self._loop.mode,
            "track_id": self._loop.track_id,
            "requested_by": self._loop.requested_by,
            "enabled_at": self._loop.enabled_at.isoformat() if self._loop.enabled_at else None,
            "until": self._loop.until.isoformat() if self._loop.until else None,
            "remaining_seconds": remaining_seconds,
        }

    def _queued_track_to_dict(self, track: QueuedTrack) -> dict[str, Any]:
        return {
            "track_id": track.track_id,
            "title": track.title,
            "artist": track.artist,
            "duration": track.duration,
            "quality": track.quality,
            "requested_by": track.requested_by,
            "requested_by_id": track.requested_by_id,
            "requested_channel_id": track.requested_channel_id,
            "source_query": track.source_query,
            "enqueued_at": track.enqueued_at.isoformat(),
        }

    def _cleanup_expired_pending_locked(self) -> None:
        now = datetime.now(timezone.utc)
        expired_keys = [key for key, pending in self._pending.items() if pending.is_expired(now)]
        for key in expired_keys:
            del self._pending[key]

    def _cleanup_expired_loop_locked(self) -> None:
        if self._loop.mode != "timed" or self._loop.until is None:
            return
        if utcnow() >= self._loop.until:
            self._loop = LoopConfig()
