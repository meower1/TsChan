from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .duration_parser import DurationParseError, parse_duration_seconds
from .errors import MelodifyAuthError, MelodifyError, TS3AudioBotError
from .melodify_client import MelodifyClient
from .queue_manager import PlaybackCoordinator
from .teamspeak_gateway import TeamSpeakGateway

LOGGER = logging.getLogger(__name__)

_ALLOWED_COMMAND_TARGET_MODES = {"1", "2", "3"}


@dataclass(frozen=True)
class CommandContext:
    raw: dict[str, Any]
    invoker_id: str
    invoker_name: str
    target_mode: str
    message: str


class CommandService:
    def __init__(
        self,
        *,
        prefix: str,
        coordinator: PlaybackCoordinator,
        melodify: MelodifyClient,
        gateway: TeamSpeakGateway,
        playback_allowed_server_group_ids: set[str] | None = None,
    ) -> None:
        self._prefix = prefix
        self._coordinator = coordinator
        self._melodify = melodify
        self._gateway = gateway
        self._playback_allowed_server_group_ids = playback_allowed_server_group_ids or set()

    async def handle(self, bot: Any, ctx: CommandContext) -> None:
        if not ctx.message.startswith(self._prefix):
            return

        command_line = ctx.message[len(self._prefix) :].strip()
        if not command_line:
            return

        if ctx.target_mode not in _ALLOWED_COMMAND_TARGET_MODES:
            await self._reply(
                bot,
                ctx,
                (
                    "Use private, channel, or server chat for commands. "
                    "Channel chat may be used when you are in the same voice channel as the bot."
                ),
            )
            return

        try:
            parts = shlex.split(command_line)
        except ValueError:
            await self._reply(bot, ctx, "Invalid command syntax.")
            return

        if not parts:
            return

        command = parts[0].lower()
        args = parts[1:]

        invoker = await self._gateway.get_invoker_state(ctx.invoker_id)
        if invoker is None:
            await self._reply(bot, ctx, "Could not resolve your TeamSpeak session. Try again.")
            return

        if command != "summon" and not self._can_play_music(invoker.server_groups):
            await self._reply(bot, ctx, "You need the Member role or above to control music.")
            LOGGER.info(
                "command rejected due to server group",
                extra={
                    "event": "command_rejected",
                    "invoker_id": ctx.invoker_id,
                    "command": command,
                    "decision": "reject",
                    "reason": "server_group",
                },
            )
            return

        presence = await self._gateway.resolve_presence()
        await self._coordinator.update_presence(
            bot_online=presence.bot.online,
            bot_channel_id=presence.bot.channel_id,
            active_human_users=presence.active_human_users,
        )

        LOGGER.info(
            "command received",
            extra={
                "event": "command_received",
                "invoker_id": ctx.invoker_id,
                "invoker_channel": invoker.channel_id,
                "bot_channel": presence.bot.channel_id,
                "command": command,
                "decision": "received",
            },
        )

        try:
            if command != "summon":
                if not presence.bot.online:
                    await self._reply(
                        bot,
                        ctx,
                        "Audio bot is offline. Ask an allowed admin to run !summon.",
                    )
                    LOGGER.info(
                        "command rejected while audio bot offline",
                        extra={
                            "event": "command_rejected",
                            "invoker_id": ctx.invoker_id,
                            "command": command,
                            "decision": "reject",
                            "reason": "audio_bot_offline",
                        },
                    )
                    return

                if invoker.channel_id is None or invoker.channel_id != presence.bot.channel_id:
                    await self._reply(
                        bot,
                        ctx,
                        "You must be in the same voice channel as the bot.",
                    )
                    LOGGER.info(
                        "command rejected due to room mismatch",
                        extra={
                            "event": "command_rejected",
                            "invoker_id": ctx.invoker_id,
                            "invoker_channel": invoker.channel_id,
                            "bot_channel": presence.bot.channel_id,
                            "command": command,
                            "decision": "reject",
                            "reason": "not_same_voice_channel",
                        },
                    )
                    return

            if command in {"help", "mhelp"}:
                await self._cmd_help(bot, ctx)
            elif command == "play":
                await self._cmd_play(bot, ctx, invoker.channel_id, args)
            elif command == "pick":
                await self._cmd_pick(bot, ctx, invoker.channel_id, args)
            elif command == "queue":
                await self._cmd_queue(bot, ctx)
            elif command == "now":
                await self._cmd_now(bot, ctx)
            elif command == "skip":
                await self._cmd_skip(bot, ctx)
            elif command == "stop":
                await self._cmd_stop(bot, ctx)
            elif command == "loop":
                await self._cmd_loop(bot, ctx, args)
            elif command == "summon":
                await self._cmd_summon(bot, ctx, invoker.channel_id, invoker.server_groups, presence)
            else:
                await self._reply(
                    bot,
                    ctx,
                    (
                        f"Unknown command. Use {self._prefix}play, {self._prefix}pick, "
                        f"{self._prefix}queue, {self._prefix}now, {self._prefix}skip, "
                        f"{self._prefix}stop, {self._prefix}loop, {self._prefix}summon"
                    ),
                )
        except ValueError as exc:
            await self._reply(bot, ctx, str(exc))
        except (MelodifyAuthError, MelodifyError, TS3AudioBotError):
            LOGGER.exception(
                "upstream command failure",
                extra={
                    "event": "command_failed",
                    "invoker_id": ctx.invoker_id,
                    "command": command,
                    "decision": "fail",
                    "reason": "upstream",
                },
            )
            await self._reply(bot, ctx, "Command failed due to an upstream service error.")
        except Exception:
            LOGGER.exception(
                "internal command failure",
                extra={
                    "event": "command_failed",
                    "invoker_id": ctx.invoker_id,
                    "command": command,
                    "decision": "fail",
                    "reason": "internal",
                },
            )
            await self._reply(bot, ctx, "Internal error while processing command.")

    async def _cmd_play(self, bot: Any, ctx: CommandContext, channel_id: str | None, args: list[str]) -> None:
        if channel_id is None:
            raise ValueError("You must be connected to a voice channel.")

        if not args:
            await self._reply(bot, ctx, f"Usage: {self._prefix}play <search query>")
            return

        query = " ".join(args).strip()
        tracks = await self._melodify.search_tracks(query, limit=5)
        if not tracks:
            await self._reply(bot, ctx, f"No results for '{query}'.")
            return

        pending = await self._coordinator.add_pending_pick(
            channel_id=channel_id,
            invoker_id=ctx.invoker_id,
            invoker_name=ctx.invoker_name,
            query=query,
            tracks=tracks,
        )

        lines = [f"Top results for '{query}':"]
        for index, track in enumerate(tracks, start=1):
            artist = f" - {track.artist}" if track.artist else ""
            lines.append(f"{index}. {track.title}{artist} (id:{track.track_id})")

        ttl_seconds = int((pending.expires_at - pending.created_at).total_seconds())
        lines.append(f"Reply with {self._prefix}pick <1-{len(tracks)}> within {ttl_seconds}s")
        await self._reply(bot, ctx, "\n".join(lines))

    async def _cmd_help(self, bot: Any, ctx: CommandContext) -> None:
        await self._reply(
            bot,
            ctx,
            "\n".join(
                [
                    f"{self._prefix}play <search query> - search Melodify",
                    f"{self._prefix}pick <1-5> - queue one of the search results",
                    f"{self._prefix}queue - show queue",
                    f"{self._prefix}now - show current track",
                    f"{self._prefix}skip - skip current track",
                    f"{self._prefix}stop - stop playback and clear queue",
                    f"{self._prefix}loop off|inf|<duration> - loop current track",
                    f"{self._prefix}summon - move the bot to your channel",
                ]
            ),
        )

    async def _cmd_pick(self, bot: Any, ctx: CommandContext, channel_id: str | None, args: list[str]) -> None:
        if channel_id is None:
            raise ValueError("You must be connected to a voice channel.")

        if len(args) != 1:
            await self._reply(bot, ctx, f"Usage: {self._prefix}pick <1-5>")
            return

        try:
            pick_index = int(args[0])
        except ValueError:
            await self._reply(bot, ctx, f"Pick must be a number, e.g. {self._prefix}pick 2")
            return

        queued = await self._coordinator.pick_track(
            channel_id=channel_id,
            invoker_id=ctx.invoker_id,
            invoker_name=ctx.invoker_name,
            pick_index=pick_index,
        )
        await self._reply(
            bot,
            ctx,
            f"Queued: {queued.title} ({queued.quality} kbps) requested by {queued.requested_by}",
        )

    async def _cmd_queue(self, bot: Any, ctx: CommandContext) -> None:
        snapshot = await self._coordinator.state_snapshot()
        current = snapshot.get("current")
        queue = snapshot.get("queue", [])

        lines: list[str] = []
        if current:
            current_track = current["track"]
            lines.append(f"Now: {current_track['title']} ({current_track['quality']})")
        else:
            lines.append("Now: idle")

        lines.append(self._loop_status_line(snapshot))

        if not queue:
            lines.append("Queue: empty")
        else:
            lines.append("Queue:")
            for index, track in enumerate(queue[:10], start=1):
                lines.append(f"{index}. {track['title']} ({track['quality']})")

        await self._reply(bot, ctx, "\n".join(lines))

    async def _cmd_now(self, bot: Any, ctx: CommandContext) -> None:
        snapshot = await self._coordinator.state_snapshot()
        current = snapshot.get("current")
        if not current:
            await self._reply(bot, ctx, "No track is playing.")
            return

        track = current["track"]
        await self._reply(
            bot,
            ctx,
            (
                f"Now playing: {track['title']} ({track['quality']}) requested by {track['requested_by']}\n"
                f"{self._loop_status_line(snapshot)}"
            ),
        )

    async def _cmd_skip(self, bot: Any, ctx: CommandContext) -> None:
        skipped = await self._coordinator.skip_current()
        if skipped:
            await self._reply(bot, ctx, "Skipped current track and disabled loop.")
        else:
            await self._reply(bot, ctx, "Nothing to skip.")

    async def _cmd_stop(self, bot: Any, ctx: CommandContext) -> None:
        await self._coordinator.stop_all()
        await self._reply(bot, ctx, "Stopped playback, cleared queue, and disabled loop.")

    async def _cmd_loop(self, bot: Any, ctx: CommandContext, args: list[str]) -> None:
        if len(args) != 1:
            await self._reply(bot, ctx, f"Usage: {self._prefix}loop off|inf|<duration>")
            return

        raw = args[0].strip().lower()
        if raw in {"off", "disable", "none"}:
            await self._coordinator.disable_loop()
            await self._reply(bot, ctx, "Loop disabled.")
            return

        if raw in {"inf", "infinite", "forever"}:
            await self._coordinator.configure_loop_for_current(
                requested_by=ctx.invoker_name,
                duration_seconds=None,
            )
            await self._reply(bot, ctx, "Loop enabled for the current track (infinite).")
            return

        try:
            seconds = parse_duration_seconds(raw)
        except DurationParseError as exc:
            await self._reply(bot, ctx, str(exc))
            return

        loop_state = await self._coordinator.configure_loop_for_current(
            requested_by=ctx.invoker_name,
            duration_seconds=seconds,
        )
        remaining = int(loop_state.get("remaining_seconds") or seconds)
        await self._reply(
            bot,
            ctx,
            f"Loop enabled for current track for {self._format_remaining(remaining)}.",
        )

    async def _cmd_summon(
        self,
        bot: Any,
        ctx: CommandContext,
        invoker_channel_id: str | None,
        invoker_server_groups: set[str],
        presence,
    ) -> None:
        if not self._gateway.can_summon(invoker_server_groups):
            await self._reply(bot, ctx, "You are not allowed to use summon.")
            return

        if invoker_channel_id is None:
            await self._reply(bot, ctx, "Join a voice channel before using summon.")
            return

        if presence.bot.online and presence.bot.client_id:
            if presence.bot.channel_id != invoker_channel_id:
                await self._gateway.move_client(
                    client_id=presence.bot.client_id,
                    channel_id=invoker_channel_id,
                )
                await self._coordinator.clear_pending_summon()
                await self._reply(bot, ctx, "Bot moved to your voice channel.")
            else:
                await self._coordinator.clear_pending_summon()
                await self._reply(bot, ctx, "Bot is already in your voice channel.")
            return

        await self._coordinator.set_pending_summon(
            channel_id=invoker_channel_id,
            requested_by_id=ctx.invoker_id,
            requested_by_name=ctx.invoker_name,
        )
        await self._reply(
            bot,
            ctx,
            "Bot is currently offline. Summon request queued and will apply on reconnect.",
        )

    def _loop_status_line(self, snapshot: dict[str, Any]) -> str:
        loop_state = snapshot.get("loop_state") or {}
        if not loop_state.get("enabled"):
            return "Loop: off"

        mode = loop_state.get("mode")
        if mode == "inf":
            return "Loop: current track (infinite)"

        remaining = loop_state.get("remaining_seconds")
        if isinstance(remaining, int) and remaining > 0:
            return f"Loop: current track ({self._format_remaining(remaining)} left)"

        until = loop_state.get("until")
        if until:
            return f"Loop: current track (until {until})"

        return "Loop: current track"

    @staticmethod
    def _format_remaining(seconds: int) -> str:
        delta = timedelta(seconds=max(seconds, 0))
        total = int(delta.total_seconds())
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h{minutes:02d}m"
        if minutes > 0:
            return f"{minutes}m{secs:02d}s"
        return f"{secs}s"

    async def _reply(self, bot: Any, ctx: CommandContext, message: str) -> None:
        try:
            await bot.respond(ctx.raw, message[:7000])
        except Exception:
            LOGGER.exception("failed sending command response", extra={"event": "command_response_failed"})

    def _can_play_music(self, invoker_server_groups: set[str]) -> bool:
        if not self._playback_allowed_server_group_ids:
            return True
        return bool(self._playback_allowed_server_group_ids.intersection(invoker_server_groups))
