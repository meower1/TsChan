from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from melodify_ts_bot.command_service import CommandContext, CommandService


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def respond(self, _ctx: dict[str, Any], message: str) -> None:
        self.messages.append(message)


class FakeCoordinator:
    def __init__(self) -> None:
        self.pending_summon: dict[str, str] | None = None
        self.presence_updates: list[dict[str, Any]] = []

    async def update_presence(self, *, bot_online: bool, bot_channel_id: str | None, active_human_users: int) -> None:
        self.presence_updates.append(
            {
                "bot_online": bot_online,
                "bot_channel_id": bot_channel_id,
                "active_human_users": active_human_users,
            }
        )

    async def state_snapshot(self) -> dict[str, Any]:
        return {
            "current": None,
            "queue": [],
            "loop_state": {"enabled": False},
        }

    async def skip_current(self) -> bool:
        return False

    async def stop_all(self) -> None:
        return None

    async def disable_loop(self) -> None:
        return None

    async def configure_loop_for_current(self, *, requested_by: str, duration_seconds: int | None) -> dict[str, Any]:
        return {"remaining_seconds": duration_seconds}

    async def set_pending_summon(
        self,
        *,
        channel_id: str,
        requested_by_id: str,
        requested_by_name: str,
    ) -> None:
        self.pending_summon = {
            "channel_id": channel_id,
            "requested_by_id": requested_by_id,
            "requested_by_name": requested_by_name,
        }

    async def clear_pending_summon(self) -> None:
        self.pending_summon = None


class FakeGateway:
    def __init__(
        self,
        *,
        invoker_channel: str | None,
        invoker_groups: set[str],
        bot_online: bool,
        bot_channel: str | None,
        bot_client_id: str | None,
        summon_allowed: bool,
    ) -> None:
        self._invoker_channel = invoker_channel
        self._invoker_groups = invoker_groups
        self._presence = SimpleNamespace(
            bot=SimpleNamespace(
                online=bot_online,
                channel_id=bot_channel,
                client_id=bot_client_id,
            ),
            active_human_users=1,
        )
        self._summon_allowed = summon_allowed
        self.moved: dict[str, str] | None = None

    async def get_invoker_state(self, _invoker_id: str):
        return SimpleNamespace(
            channel_id=self._invoker_channel,
            server_groups=self._invoker_groups,
        )

    async def resolve_presence(self):
        return self._presence

    def can_summon(self, _invoker_server_groups: set[str]) -> bool:
        return self._summon_allowed

    async def move_client(self, *, client_id: str, channel_id: str) -> None:
        self.moved = {"client_id": client_id, "channel_id": channel_id}


class FakeMelodify:
    async def search_tracks(self, _query: str, *, limit: int = 5):
        return []


@pytest.mark.asyncio
async def test_non_summon_requires_same_room() -> None:
    coordinator = FakeCoordinator()
    gateway = FakeGateway(
        invoker_channel="20",
        invoker_groups={"6"},
        bot_online=True,
        bot_channel="10",
        bot_client_id="42",
        summon_allowed=True,
    )
    service = CommandService(
        prefix="!",
        coordinator=coordinator,
        melodify=FakeMelodify(),
        gateway=gateway,
    )
    bot = FakeBot()

    ctx = CommandContext(
        raw={"invokerid": "2"},
        invoker_id="2",
        invoker_name="user",
        target_mode="1",
        message="!queue",
    )

    await service.handle(bot, ctx)

    assert bot.messages
    assert "same voice channel" in bot.messages[-1]


@pytest.mark.asyncio
async def test_summon_requires_allowed_group() -> None:
    coordinator = FakeCoordinator()
    gateway = FakeGateway(
        invoker_channel="20",
        invoker_groups={"8"},
        bot_online=False,
        bot_channel=None,
        bot_client_id=None,
        summon_allowed=False,
    )
    service = CommandService(
        prefix="!",
        coordinator=coordinator,
        melodify=FakeMelodify(),
        gateway=gateway,
    )
    bot = FakeBot()

    ctx = CommandContext(
        raw={"invokerid": "2"},
        invoker_id="2",
        invoker_name="user",
        target_mode="1",
        message="!summon",
    )

    await service.handle(bot, ctx)

    assert bot.messages
    assert "not allowed" in bot.messages[-1]
    assert coordinator.pending_summon is None


@pytest.mark.asyncio
async def test_offline_summon_sets_pending_request() -> None:
    coordinator = FakeCoordinator()
    gateway = FakeGateway(
        invoker_channel="20",
        invoker_groups={"6"},
        bot_online=False,
        bot_channel=None,
        bot_client_id=None,
        summon_allowed=True,
    )
    service = CommandService(
        prefix="!",
        coordinator=coordinator,
        melodify=FakeMelodify(),
        gateway=gateway,
    )
    bot = FakeBot()

    ctx = CommandContext(
        raw={"invokerid": "2"},
        invoker_id="2",
        invoker_name="user",
        target_mode="1",
        message="!summon",
    )

    await service.handle(bot, ctx)

    assert coordinator.pending_summon is not None
    assert coordinator.pending_summon["channel_id"] == "20"
    assert "queued" in bot.messages[-1]
