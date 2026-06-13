from __future__ import annotations

import asyncio

import pytest

from melodify_ts_bot.stream_proxy import StreamRelayGone, StreamRelayStore


@pytest.mark.asyncio
async def test_relay_token_single_use() -> None:
    store = StreamRelayStore(ttl_seconds=60)
    token, _ = await store.issue("123", "320")

    grant = await store.consume(token)
    assert grant.track_id == "123"
    assert grant.quality == "320"
    assert grant.last_used_at is not None
    assert grant.used_count == 1

    with pytest.raises(StreamRelayGone):
        await store.consume(token)


@pytest.mark.asyncio
async def test_relay_token_expiry() -> None:
    store = StreamRelayStore(ttl_seconds=0)
    token, _ = await store.issue("123", "320")
    await asyncio.sleep(0.01)

    with pytest.raises(StreamRelayGone):
        await store.consume(token)


@pytest.mark.asyncio
async def test_relay_token_multi_use() -> None:
    store = StreamRelayStore(ttl_seconds=60, max_uses=3)
    token, _ = await store.issue("123", "320")

    await store.consume(token)
    await store.consume(token)
    grant = await store.consume(token)
    assert grant.used_count == 3

    with pytest.raises(StreamRelayGone):
        await store.consume(token)
