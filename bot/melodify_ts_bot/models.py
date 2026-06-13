from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(slots=True)
class SearchTrack:
    track_id: str
    title: str
    artist: str | None
    duration: int | None
    available_qualities: list[str]


@dataclass(slots=True)
class QueuedTrack:
    track_id: str
    title: str
    artist: str | None
    duration: int | None
    quality: str
    requested_by: str
    requested_by_id: str
    requested_channel_id: str
    source_query: str
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class PendingPick:
    channel_id: str
    invoker_id: str
    invoker_name: str
    query: str
    created_at: datetime
    expires_at: datetime
    tracks: list[SearchTrack]

    def is_expired(self, now: datetime | None = None) -> bool:
        now_dt = now or datetime.now(timezone.utc)
        return now_dt >= self.expires_at


@dataclass(slots=True)
class CurrentPlayback:
    track: QueuedTrack
    stream_url: str
    stream_expires_at: datetime | None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class StreamTokenResult:
    stream_url: str
    expires_at: datetime | None
    title: str | None = None
    artist: str | None = None
    duration: int | None = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utc_plus(seconds: int) -> datetime:
    return utcnow() + timedelta(seconds=seconds)
