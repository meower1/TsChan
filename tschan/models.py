"""Shared data models used by both engine and TUI layers."""

from __future__ import annotations

import json
import secrets
import string
from dataclasses import asdict, dataclass, field
from typing import Any


def _generate_token(length: int = 48) -> str:
    """Generate a cryptographically secure random token.

    Args:
        length: Number of characters in the token.

    Returns:
        A string of random alphanumeric characters.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class SetupConfig:
    """Full configuration for a tschan server deployment.

    Attributes:
        server_name: Human-readable name used in the TS3 server title.
        music_bot_enabled: Whether to deploy ts3audiobot + orchestrator.
        melodify_api_key: API key for the Melodify music service.
        template_name: One of meowers_hangout, neon_arena, cozy_den.
        role_groups: List of role category keys to create (e.g. ["staff", "games"]).
        welcome_message: Message shown to users on connect.
        iran_mirrors: Whether to use Iranian Docker/pip mirrors.
        query_password: Auto-generated ServerQuery admin password.
        debug_token: Auto-generated debug/API token.
    """

    server_name: str = ""
    music_bot_enabled: bool = False
    melodify_api_key: str = ""
    template_name: str = "meowers_hangout"
    role_groups: list[str] = field(default_factory=lambda: ["staff"])
    welcome_message: str = "Welcome to the server!"
    iran_mirrors: bool = False
    # Auto-generated on creation:
    query_password: str = field(default_factory=lambda: _generate_token(48))
    debug_token: str = field(default_factory=lambda: _generate_token(48))

    _VALID_TEMPLATES = ("meowers_hangout", "neon_arena", "cozy_den")

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list means valid.

        Returns:
            List of human-readable error strings.
        """
        errors: list[str] = []
        if not self.server_name.strip():
            errors.append("Server name is required")
        if self.music_bot_enabled and not self.melodify_api_key.strip():
            errors.append(
                "Melodify API key is required when music bot is enabled"
            )
        if self.template_name not in self._VALID_TEMPLATES:
            errors.append(f"Unknown template: {self.template_name}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (suitable for JSON)."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SetupConfig:
        """Deserialize from a plain dict.

        Unknown keys are silently ignored so older state files don't break.
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, text: str) -> SetupConfig:
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(text))


@dataclass
class ContainerInfo:
    """Information about a single Docker container.

    Attributes:
        name: Container name (e.g. "ts3-server").
        state: Current state string (running, exited, created, …).
        health: Health status (healthy, unhealthy, starting, none).
        status: Human-readable status line (e.g. "Up 2 hours").
    """

    name: str
    state: str
    health: str
    status: str


@dataclass
class ServerInfo:
    """Live information from a running TS3 virtual server.

    Attributes:
        name: Virtual server name.
        clients_online: Number of currently connected clients.
        max_clients: Maximum allowed clients.
        uptime_seconds: Server uptime in seconds.
        version: TS3 server version string.
        platform: Platform identifier (e.g. "Linux").
    """

    name: str
    clients_online: int
    max_clients: int
    uptime_seconds: int
    version: str
    platform: str
