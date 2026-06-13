from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from typing import Any

from tsbot import query_builder

from .command_service import CommandContext, CommandService
from .logging_utils import set_request_id
from .queue_manager import PlaybackCoordinator
from .teamspeak_gateway import TeamSpeakGateway
from .ts3audiobot_client import TS3AudioBotClient

LOGGER = logging.getLogger(__name__)


class TeamSpeakCommandRuntime:
    def __init__(
        self,
        *,
        address: str,
        username: str,
        password: str,
        server_id: int,
        query_port: int,
        prefix: str,
        coordinator: PlaybackCoordinator,
        command_service: CommandService,
        gateway: TeamSpeakGateway,
        ts3audiobot: TS3AudioBotClient,
        presence_poll_seconds: float,
    ) -> None:
        self._prefix = prefix
        self._coordinator = coordinator
        self._command_service = command_service
        self._gateway = gateway
        self._ts3audiobot = ts3audiobot
        self._presence_poll_seconds = max(presence_poll_seconds, 0.5)
        self._next_reconnect_attempt_monotonic = 0.0

        from tsbot import TSBot

        self._tsbot_module = TSBot
        self._bot = self._build_bot(
            address=address,
            username=username,
            password=password,
            server_id=server_id,
            query_port=query_port,
            prefix=prefix,
        )
        self._gateway.bind_runtime_bot(self._bot)
        self._register_events()

    def _build_bot(
        self,
        *,
        address: str,
        username: str,
        password: str,
        server_id: int,
        query_port: int,
        prefix: str,
    ):
        TSBot = self._tsbot_module
        signature = inspect.signature(TSBot)
        kwargs: dict[str, Any] = {}
        candidates = {
            "address": address,
            "host": address,
            "username": username,
            "password": password,
            "port": query_port,
            "query_port": query_port,
            "server_id": server_id,
            "sid": server_id,
            "prefix": prefix,
            "command_prefix": prefix,
            "invoker": prefix,
        }
        for key, value in candidates.items():
            if key in signature.parameters:
                kwargs[key] = value

        if "address" not in kwargs and "host" not in kwargs:
            kwargs["address"] = address
        if "username" not in kwargs:
            kwargs["username"] = username
        if "password" not in kwargs:
            kwargs["password"] = password

        return TSBot(**kwargs)

    def _register_events(self) -> None:
        @self._bot.on("connect")
        async def on_connect(bot, _ctx=None):
            await self._move_query_to_audio_bot_channel()
            await self._register_channel_text_notifications()

        @self._bot.on("textmessage")
        async def on_textmessage(bot, raw_ctx):
            ctx = self._parse_context(raw_ctx)
            LOGGER.info(
                "text message received",
                extra={
                    "event": "text_message_received",
                    "invoker_id": ctx.invoker_id,
                    "channel_id": ctx.raw.get("ctid") or ctx.raw.get("target") or "",
                    "targetmode": str(raw_ctx.get("targetmode", "")),
                    "prefix_match": ctx.message.startswith(self._prefix),
                },
            )
            if not ctx.message.startswith(self._prefix):
                return

            request_id = f"cmd-{ctx.invoker_id}-{int(time.time() * 1000)}"
            set_request_id(request_id)
            try:
                await self._command_service.handle(bot, ctx)
            finally:
                set_request_id(None)

    def _parse_context(self, raw_ctx: dict[str, Any]) -> CommandContext:
        invoker_id = str(raw_ctx.get("invokerid", "unknown"))
        invoker_name = str(raw_ctx.get("invokername", "unknown"))
        message = str(raw_ctx.get("msg", "")).strip()
        target_mode = str(raw_ctx.get("targetmode", ""))

        return CommandContext(
            raw=raw_ctx,
            invoker_id=invoker_id,
            invoker_name=invoker_name,
            target_mode=target_mode,
            message=message,
        )

    async def _unregister_channel_text_notifications(self) -> None:
        """Clear previous servernotifyregister subscriptions to prevent duplicates on reconnect."""
        try:
            await self._bot.send(
                query_builder.TSQuery(
                    "servernotifyunregister",
                    parameters={"event": "textchannel"},
                )
            )
        except Exception:
            # Older TS3 servers may not support servernotifyunregister;
            # not fatal — we still re-register below.
            LOGGER.debug(
                "servernotifyunregister not supported or failed (non-fatal)",
                extra={"event": "channel_text_unregister_skipped"},
            )

    async def _register_channel_text_notifications(self) -> None:
        try:
            await self._unregister_channel_text_notifications()

            response = await self._bot.send(query_builder.TSQuery("channellist"))
            channel_ids = [str(row.get("cid")) for row in response.data if row.get("cid")]
            for channel_id in channel_ids:
                await self._bot.send(
                    query_builder.TSQuery(
                        "servernotifyregister",
                        parameters={
                            "event": "textchannel",
                            "id": channel_id,
                        },
                    )
                )
            LOGGER.info(
                "registered channel text notifications",
                extra={
                    "event": "channel_text_notifications_registered",
                    "channel_count": len(channel_ids),
                },
            )
        except Exception:
            LOGGER.exception(
                "failed registering channel text notifications",
                extra={"event": "channel_text_notifications_failed"},
            )

    async def _move_query_to_audio_bot_channel(self) -> None:
        bot_name = os.getenv("TS3AB_BOT_NAME", "MelodifyBot").strip() or "MelodifyBot"
        try:
            whoami = await self._bot.send(query_builder.TSQuery("whoami"))
            own_client_id = str(whoami.first.get("client_id", ""))
            own_channel_id = str(whoami.first.get("client_channel_id", ""))

            clients = await self._bot.send(query_builder.TSQuery("clientlist"))
            audio_bot_channel_id = None
            for row in clients.data:
                if str(row.get("client_type", "0")) != "0":
                    continue
                nickname = str(row.get("client_nickname", ""))
                if nickname == bot_name or nickname.startswith(f"{bot_name}("):
                    audio_bot_channel_id = str(row.get("cid", ""))
                    break

            if not own_client_id or not audio_bot_channel_id or own_channel_id == audio_bot_channel_id:
                LOGGER.info(
                    "query channel already aligned or audio bot unavailable",
                    extra={
                        "event": "query_channel_alignment",
                        "own_client_id": own_client_id,
                        "own_channel_id": own_channel_id,
                        "audio_bot_channel_id": audio_bot_channel_id,
                    },
                )
                return

            await self._bot.send(
                query_builder.TSQuery(
                    "clientmove",
                    parameters={
                        "clid": own_client_id,
                        "cid": audio_bot_channel_id,
                    },
                )
            )
            LOGGER.info(
                "moved query listener to audio bot channel",
                extra={
                    "event": "query_listener_moved",
                    "own_client_id": own_client_id,
                    "channel_id": audio_bot_channel_id,
                },
            )
        except Exception:
            LOGGER.exception(
                "failed moving query listener to audio bot channel",
                extra={"event": "query_listener_move_failed"},
            )

    async def _maintenance_loop(self) -> None:
        while True:
            loop_start = asyncio.get_event_loop().time()
            try:
                await asyncio.wait_for(
                    self._sync_presence_and_pending_summon(),
                    timeout=max(self._presence_poll_seconds * 4, 10.0),
                )
            except asyncio.TimeoutError:
                LOGGER.warning(
                    "maintenance loop timed out",
                    extra={"event": "maintenance_timeout"},
                )
            except Exception:
                LOGGER.exception("runtime maintenance loop failed")
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_time = max(0.0, self._presence_poll_seconds - elapsed)
            await asyncio.sleep(sleep_time)

    async def _sync_presence_and_pending_summon(self) -> None:
        presence = await self._gateway.resolve_presence()
        await self._coordinator.update_presence(
            bot_online=presence.bot.online,
            bot_channel_id=presence.bot.channel_id,
            active_human_users=presence.active_human_users,
        )

        pending = await self._coordinator.pending_summon_snapshot()
        if pending is None:
            return

        if not presence.bot.online or not presence.bot.client_id:
            now_monotonic = time.monotonic()
            if now_monotonic >= self._next_reconnect_attempt_monotonic:
                self._next_reconnect_attempt_monotonic = now_monotonic + 15.0
                try:
                    await self._ts3audiobot.connect()
                    LOGGER.info(
                        "attempted TS3AudioBot reconnect for pending summon",
                        extra={
                            "event": "summon_reconnect_attempt",
                            "decision": "reconnect",
                            "reason": "bot_offline",
                        },
                    )
                except Exception:
                    LOGGER.exception("failed to request TS3AudioBot reconnect")
            return

        target_channel_id = str(pending["channel_id"])
        if presence.bot.channel_id == target_channel_id:
            await self._coordinator.clear_pending_summon()
            LOGGER.info(
                "pending summon cleared because bot already in channel",
                extra={
                    "event": "summon_pending_cleared",
                    "channel_id": target_channel_id,
                    "decision": "clear",
                    "reason": "already_in_channel",
                },
            )
            return

        await self._gateway.move_client(
            client_id=presence.bot.client_id,
            channel_id=target_channel_id,
        )
        await self._coordinator.clear_pending_summon()
        LOGGER.info(
            "pending summon applied",
            extra={
                "event": "summon_applied",
                "channel_id": target_channel_id,
                "decision": "move",
                "reason": "pending_summon",
            },
        )

    async def run(self) -> None:
        self._coordinator.set_ts_connected(True)
        maintenance_task = asyncio.create_task(self._maintenance_loop(), name="ts-maintenance")
        try:
            await self._bot.run()
        finally:
            maintenance_task.cancel()
            await asyncio.gather(maintenance_task, return_exceptions=True)
            self._coordinator.set_ts_connected(False)
