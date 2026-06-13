from __future__ import annotations

import asyncio
import logging

import uvicorn

from .command_service import CommandService
from .config import load_settings
from .errors import MelodifyAuthError
from .logging_utils import configure_logging
from .melodify_client import MelodifyClient
from .ops_api import create_ops_app
from .queue_manager import PlaybackCoordinator
from .teamspeak_gateway import TeamSpeakGateway
from .stream_proxy import StreamRelayStore
from .teamspeak_runtime import TeamSpeakCommandRuntime
from .ts3audiobot_client import TS3AudioBotClient

LOGGER = logging.getLogger(__name__)


async def _startup_smoke(
    *,
    melodify: MelodifyClient,
    ts3audiobot: TS3AudioBotClient,
) -> None:
    try:
        auth = await melodify.auth_status()
        LOGGER.info(
            "startup melodify auth check",
            extra={"event": "startup_auth", "queue_len": 0},
        )
        LOGGER.debug("melodify auth payload: %s", auth)
    except MelodifyAuthError as exc:
        LOGGER.warning("startup auth check failed: %s", exc)
    except Exception:
        LOGGER.exception("startup auth check crashed")

    try:
        ready = await ts3audiobot.readiness()
        if ready:
            LOGGER.info("startup ts3audiobot check passed", extra={"event": "startup_ts3ab"})
        else:
            LOGGER.warning("startup ts3audiobot check failed")
    except Exception:
        LOGGER.exception("startup ts3audiobot check crashed")


async def _run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    stream_relay = (
        StreamRelayStore(ttl_seconds=300, max_uses=3)
        if settings.melodify_legacy_stream_fallback
        else None
    )

    async def build_legacy_stream_url(track_id: str, quality: str) -> str:
        if stream_relay is None:
            raise RuntimeError("legacy stream relay is disabled")
        token, _ = await stream_relay.issue(track_id=track_id, quality=quality)
        return f"{settings.ops_public_base_url}/internal/stream/{token}"

    melodify = MelodifyClient(
        base_url=settings.melodify_base_url,
        api_key=settings.melodify_api_key,
        legacy_stream_url_factory=build_legacy_stream_url if stream_relay is not None else None,
        force_legacy_stream_url=settings.melodify_force_legacy_stream_relay,
    )
    ts3audiobot = TS3AudioBotClient(
        base_url=settings.ts3audiobot_base_url,
        username=settings.ts3audiobot_username,
        password=settings.ts3audiobot_password,
        bot_id=settings.ts3audiobot_bot_id,
    )
    coordinator = PlaybackCoordinator(
        melodify=melodify,
        ts3audiobot=ts3audiobot,
        default_quality=settings.melodify_default_quality,
        pending_ttl_seconds=settings.pending_pick_ttl_seconds,
        poll_seconds=settings.playback_poll_seconds,
        minimum_active_users=settings.minimum_active_users_in_channel,
    )

    gateway = TeamSpeakGateway(
        audio_bot_name=settings.ts3audiobot_bot_name,
        summon_allowed_server_group_ids=set(settings.summon_allowed_server_group_ids),
    )
    command_service = CommandService(
        prefix=settings.command_prefix,
        coordinator=coordinator,
        melodify=melodify,
        gateway=gateway,
        playback_allowed_server_group_ids=set(settings.playback_allowed_server_group_ids),
    )

    runtime = TeamSpeakCommandRuntime(
        address=settings.teamspeak_address,
        username=settings.teamspeak_username,
        password=settings.teamspeak_password,
        server_id=settings.teamspeak_server_id,
        query_port=settings.teamspeak_query_port,
        prefix=settings.command_prefix,
        coordinator=coordinator,
        command_service=command_service,
        gateway=gateway,
        ts3audiobot=ts3audiobot,
        presence_poll_seconds=settings.runtime_presence_poll_seconds,
    )

    ops_app = create_ops_app(
        coordinator=coordinator,
        melodify=melodify,
        ts3audiobot=ts3audiobot,
        debug_token=settings.ops_debug_token,
        smoke_default_query=settings.smoke_default_query,
        stream_relay=stream_relay,
    )

    uvicorn_config = uvicorn.Config(
        app=ops_app,
        host=settings.ops_host,
        port=settings.ops_port,
        loop="asyncio",
        access_log=False,
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    await coordinator.start()
    if stream_relay is not None:
        await stream_relay.start()
    await _startup_smoke(melodify=melodify, ts3audiobot=ts3audiobot)

    tasks = [
        asyncio.create_task(runtime.run(), name="tsbot-runtime"),
        asyncio.create_task(uvicorn_server.serve(), name="ops-api"),
    ]

    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

        for task in done:
            exc = task.exception()
            if exc:
                raise exc

        for task in pending:
            task.cancel()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await coordinator.stop()
        if stream_relay is not None:
            await stream_relay.stop()
        await ts3audiobot.close()
        await melodify.close()


def main() -> int:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
