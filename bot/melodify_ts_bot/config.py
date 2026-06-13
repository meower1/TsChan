from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    teamspeak_address: str
    teamspeak_username: str
    teamspeak_password: str
    teamspeak_server_id: int
    teamspeak_query_port: int
    command_prefix: str

    melodify_base_url: str
    melodify_api_key: str
    melodify_default_quality: str

    ts3audiobot_base_url: str
    ts3audiobot_bot_id: int
    ts3audiobot_bot_name: str
    ts3audiobot_username: str
    ts3audiobot_password: str

    pending_pick_ttl_seconds: int
    playback_poll_seconds: float
    minimum_active_users_in_channel: int
    runtime_presence_poll_seconds: float
    playback_allowed_server_group_ids: tuple[str, ...]
    summon_allowed_server_group_ids: tuple[str, ...]

    ops_host: str
    ops_port: int
    ops_public_base_url: str
    ops_debug_token: str
    smoke_default_query: str
    melodify_legacy_stream_fallback: bool
    melodify_force_legacy_stream_relay: bool

    log_level: str


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    values = [item.strip() for item in raw.split(",")]
    return tuple(item for item in values if item)


def load_settings() -> Settings:
    return Settings(
        teamspeak_address=os.getenv("TS3_ADDRESS", "teamspeak"),
        teamspeak_username=_require_env("TS3_QUERY_USERNAME"),
        teamspeak_password=_require_env("TS3_QUERY_PASSWORD"),
        teamspeak_server_id=int(os.getenv("TS3_SERVER_ID", "1")),
        teamspeak_query_port=int(os.getenv("TS3_QUERY_PORT", "10011")),
        command_prefix=os.getenv("TS3_COMMAND_PREFIX", "!").strip() or "!",
        melodify_base_url=os.getenv("MELODIFY_BASE_URL", "https://mel.meower1.dev").rstrip("/"),
        melodify_api_key=_require_env("MELODIFY_API_KEY"),
        melodify_default_quality=os.getenv("MELODIFY_DEFAULT_QUALITY", "320"),
        ts3audiobot_base_url=os.getenv("TS3AB_BASE_URL", "http://ts3audiobot:58913").rstrip("/"),
        ts3audiobot_bot_id=int(os.getenv("TS3AB_BOT_ID", "0")),
        ts3audiobot_bot_name=os.getenv("TS3AB_BOT_NAME", "MelodifyBot").strip() or "MelodifyBot",
        ts3audiobot_username=os.getenv("TS3AB_USERNAME", "").strip(),
        ts3audiobot_password=os.getenv("TS3AB_PASSWORD", "").strip(),
        pending_pick_ttl_seconds=int(os.getenv("PENDING_PICK_TTL_SECONDS", "90")),
        playback_poll_seconds=float(os.getenv("PLAYBACK_POLL_SECONDS", "2")),
        minimum_active_users_in_channel=max(1, int(os.getenv("MIN_ACTIVE_USERS_IN_CHANNEL", "1"))),
        runtime_presence_poll_seconds=float(os.getenv("RUNTIME_PRESENCE_POLL_SECONDS", "2")),
        playback_allowed_server_group_ids=_env_csv("PLAYBACK_ALLOWED_SERVER_GROUP_IDS", "3,6,7,11,12"),
        summon_allowed_server_group_ids=_env_csv("SUMMON_ALLOWED_SERVER_GROUP_IDS", "6"),
        ops_host=os.getenv("OPS_HOST", "0.0.0.0"),
        ops_port=int(os.getenv("OPS_PORT", "8090")),
        ops_public_base_url=os.getenv(
            "OPS_PUBLIC_BASE_URL",
            "http://python-orchestrator:8090",
        ).rstrip("/"),
        ops_debug_token=_require_env("OPS_DEBUG_TOKEN"),
        smoke_default_query=os.getenv("SMOKE_DEFAULT_QUERY", "top hit"),
        melodify_legacy_stream_fallback=_env_bool("MELODIFY_LEGACY_STREAM_FALLBACK", True),
        melodify_force_legacy_stream_relay=_env_bool("MELODIFY_FORCE_LEGACY_STREAM_RELAY", False),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
