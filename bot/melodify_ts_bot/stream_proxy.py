from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime

from .models import utc_plus, utcnow


class StreamRelayGone(Exception):
    pass


@dataclass(slots=True)
class StreamRelayGrant:
    track_id: str
    quality: str
    expires_at: datetime
    max_uses: int = 1
    used_count: int = 0
    last_used_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or utcnow()) >= self.expires_at


class StreamRelayStore:
    def __init__(self, ttl_seconds: int = 300, max_uses: int = 1) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_uses = max_uses
        self._lock = asyncio.Lock()
        self._grants: dict[str, StreamRelayGrant] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(
                self._periodic_cleanup(), name="stream-relay-cleanup"
            )

    async def stop(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _periodic_cleanup(self) -> None:
        while True:
            await asyncio.sleep(60)
            async with self._lock:
                self._cleanup_expired_locked()

    async def issue(self, track_id: str, quality: str) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(24)
        expires_at = utc_plus(self._ttl_seconds)
        grant = StreamRelayGrant(
            track_id=track_id,
            quality=quality,
            expires_at=expires_at,
            max_uses=self._max_uses,
        )

        async with self._lock:
            self._cleanup_expired_locked()
            self._grants[token] = grant

        return token, expires_at

    async def consume(self, token: str) -> StreamRelayGrant:
        async with self._lock:
            self._cleanup_expired_locked()
            grant = self._grants.get(token)
            if grant is None:
                raise StreamRelayGone("token expired or unknown")
            if grant.used_count >= grant.max_uses:
                raise StreamRelayGone("token already used")
            if grant.is_expired():
                del self._grants[token]
                raise StreamRelayGone("token expired")

            grant.used_count += 1
            grant.last_used_at = utcnow()
            return grant

    def _cleanup_expired_locked(self) -> None:
        now = utcnow()
        expired = [token for token, grant in self._grants.items() if grant.is_expired(now)]
        for token in expired:
            del self._grants[token]
