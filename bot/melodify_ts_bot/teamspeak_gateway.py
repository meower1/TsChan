from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from tsbot import query_builder

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvokerState:
    client_id: str
    channel_id: str | None
    server_groups: set[str]
    client_type: str


@dataclass(frozen=True)
class AudioBotState:
    online: bool
    client_id: str | None
    channel_id: str | None
    nickname: str | None


@dataclass(frozen=True)
class VoicePresence:
    bot: AudioBotState
    active_human_users: int


class TeamSpeakGateway:
    def __init__(
        self,
        *,
        audio_bot_name: str,
        summon_allowed_server_group_ids: set[str],
    ) -> None:
        self._audio_bot_name = audio_bot_name.strip()
        self._summon_allowed_server_group_ids = summon_allowed_server_group_ids
        self._bot: Any = None

    def bind_runtime_bot(self, bot: Any) -> None:
        self._bot = bot

    def can_summon(self, invoker_server_groups: set[str]) -> bool:
        if not self._summon_allowed_server_group_ids:
            return False
        return bool(self._summon_allowed_server_group_ids.intersection(invoker_server_groups))

    async def get_invoker_state(self, invoker_id: str) -> InvokerState | None:
        try:
            response = await self._send(
                "clientinfo",
                parameters={"clid": invoker_id},
            )
        except Exception:
            LOGGER.exception("failed resolving invoker state", extra={"event": "invoker_state_failed"})
            return None

        row = response.first
        groups_raw = row.get("client_servergroups", "")
        groups = {item for item in groups_raw.split(",") if item}
        return InvokerState(
            client_id=invoker_id,
            channel_id=row.get("cid"),
            server_groups=groups,
            client_type=str(row.get("client_type", "0")),
        )

    async def resolve_presence(self) -> VoicePresence:
        bot_state = await self.get_audio_bot_state()
        if not bot_state.online or not bot_state.channel_id:
            return VoicePresence(bot=bot_state, active_human_users=0)

        active_humans = await self.count_human_users_in_channel(
            bot_state.channel_id,
            exclude_client_ids={bot_state.client_id} if bot_state.client_id else set(),
        )
        return VoicePresence(bot=bot_state, active_human_users=active_humans)

    async def get_audio_bot_state(self) -> AudioBotState:
        try:
            response = await self._send("clientlist", options=("groups",))
        except Exception:
            LOGGER.exception("failed resolving audio bot state", extra={"event": "audiobot_state_failed"})
            return AudioBotState(online=False, client_id=None, channel_id=None, nickname=None)

        exact_match: dict[str, str] | None = None
        fallback_match: dict[str, str] | None = None

        for row in response.data:
            if str(row.get("client_type", "0")) != "0":
                continue
            nickname = str(row.get("client_nickname", ""))
            if not nickname:
                continue

            if nickname == self._audio_bot_name:
                exact_match = row
                break

            if nickname.startswith(f"{self._audio_bot_name}(") and fallback_match is None:
                fallback_match = row

        chosen = exact_match or fallback_match
        if chosen is None:
            return AudioBotState(online=False, client_id=None, channel_id=None, nickname=None)

        return AudioBotState(
            online=True,
            client_id=chosen.get("clid"),
            channel_id=chosen.get("cid"),
            nickname=chosen.get("client_nickname"),
        )

    async def count_human_users_in_channel(
        self,
        channel_id: str,
        *,
        exclude_client_ids: set[str],
    ) -> int:
        try:
            response = await self._send("clientlist")
        except Exception:
            LOGGER.exception("failed counting users", extra={"event": "channel_user_count_failed"})
            return 0

        count = 0
        for row in response.data:
            if str(row.get("client_type", "0")) != "0":
                continue
            if row.get("cid") != channel_id:
                continue
            clid = row.get("clid")
            if clid in exclude_client_ids:
                continue
            count += 1
        return count

    async def move_client(self, *, client_id: str, channel_id: str) -> None:
        await self._send(
            "clientmove",
            parameters={
                "clid": client_id,
                "cid": channel_id,
            },
        )

    async def _send(
        self,
        command: str,
        *,
        options: tuple[str, ...] | None = None,
        parameters: dict[str, str] | None = None,
    ):
        if self._bot is None:
            raise RuntimeError("TeamSpeak runtime bot is not bound")

        query = query_builder.TSQuery(command, parameters=parameters or None)
        if options:
            query = query.option(*options)

        return await self._bot.send(query)
