"""Config file generator for tschan.

Generates ``.env``, ``docker-compose.yml``, support files, and persists the
``SetupConfig`` to ``.tschan.json`` for later use by the management panel.

Public API
----------
- ``generate_env(config)`` — returns ``.env`` file content as a string.
- ``generate_docker_compose(config)`` — returns ``docker-compose.yml`` as a string.
- ``write_all(config, project_dir)`` — writes every generated file to disk.
- ``load_config(project_dir)`` — loads a previously saved ``SetupConfig``.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from tschan.constants import (
    COMPOSE_FILE,
    DATA_DIR,
    DEFAULT_FILE_PORT,
    DEFAULT_MAX_CLIENTS,
    DEFAULT_PIP_INDEX,
    DEFAULT_PYTHON_IMAGE,
    DEFAULT_QUERY_PORT_RAW,
    DEFAULT_QUERY_PORT_SSH,
    DEFAULT_TS3_IMAGE,
    DEFAULT_VOICE_PORT,
    DOCKER_NETWORK,
    ENV_FILE,
    IRAN_PIP_INDEX,
    IRAN_PYTHON_IMAGE,
    IRAN_TS3_IMAGE,
    QUERY_IP_ALLOWLIST,
    STATE_FILE,
    TEMPLATE_SERVER_NAME_SUFFIX,
)
from tschan.models import SetupConfig


# ── .env Generation ──────────────────────────────────────────────────────────


def generate_env(config: SetupConfig) -> str:
    """Generate the contents of the ``.env`` file.

    When the music bot is disabled, Melodify-related variables are written
    as comments so the user can enable them later without guessing the keys.

    Args:
        config: Fully populated ``SetupConfig``.

    Returns:
        The ``.env`` file content as a string.
    """
    suffix = TEMPLATE_SERVER_NAME_SUFFIX.get(config.template_name, "'s hangout")
    full_server_name = f"{config.server_name}{suffix}"

    ts3_image = IRAN_TS3_IMAGE if config.iran_mirrors else DEFAULT_TS3_IMAGE
    python_image = IRAN_PYTHON_IMAGE if config.iran_mirrors else DEFAULT_PYTHON_IMAGE
    pip_index = IRAN_PIP_INDEX if config.iran_mirrors else DEFAULT_PIP_INDEX

    lines: list[str] = [
        "# ── tschan – auto-generated .env ─────────────────────────────────",
        "",
        "# Server",
        f'TS3_SERVER_NAME="{full_server_name}"',
        f"TS3_QUERY_PASSWORD={config.query_password}",
        f"TS3_DEBUG_TOKEN={config.debug_token}",
        f"TS3_TEMPLATE={config.template_name}",
        f'TS3_WELCOME_MESSAGE="{config.welcome_message}"',
        "",
        "# Ports",
        f"TS3_VOICE_PORT={DEFAULT_VOICE_PORT}",
        f"TS3_QUERY_PORT_RAW={DEFAULT_QUERY_PORT_RAW}",
        f"TS3_QUERY_PORT_SSH={DEFAULT_QUERY_PORT_SSH}",
        f"TS3_FILE_PORT={DEFAULT_FILE_PORT}",
        f"TS3_MAX_CLIENTS={DEFAULT_MAX_CLIENTS}",
        "",
        "# Docker images",
        f"TS3_IMAGE={ts3_image}",
        f"PYTHON_IMAGE={python_image}",
        f"PIP_INDEX_URL={pip_index}",
        "",
        "# Mirrors",
        f"IRAN_MIRRORS={'true' if config.iran_mirrors else 'false'}",
        "",
    ]

    # Music bot / Melodify section
    if config.music_bot_enabled:
        lines.extend(
            [
                "# Music Bot",
                "MUSIC_BOT_ENABLED=true",
                f"MELODIFY_API_KEY={config.melodify_api_key}",
            ]
        )
    else:
        lines.extend(
            [
                "# Music Bot (disabled – uncomment to enable)",
                "# MUSIC_BOT_ENABLED=true",
                "# MELODIFY_API_KEY=your-key-here",
            ]
        )

    lines.append("")
    return "\n".join(lines)


# ── docker-compose.yml Generation ───────────────────────────────────────────


def _build_teamspeak_service(config: SetupConfig) -> dict[str, Any]:
    """Build the ``teamspeak`` service definition dict."""
    ts3_image = IRAN_TS3_IMAGE if config.iran_mirrors else DEFAULT_TS3_IMAGE

    return {
        "image": ts3_image,
        "container_name": "ts3-server",
        "restart": "unless-stopped",
        "ports": [
            f"{DEFAULT_VOICE_PORT}:{DEFAULT_VOICE_PORT}/udp",
            f"{DEFAULT_QUERY_PORT_RAW}:{DEFAULT_QUERY_PORT_RAW}",
            f"{DEFAULT_QUERY_PORT_SSH}:{DEFAULT_QUERY_PORT_SSH}",
            f"{DEFAULT_FILE_PORT}:{DEFAULT_FILE_PORT}",
        ],
        "environment": {
            "TS3SERVER_LICENSE": "accept",
            "TS3SERVER_QUERY_PROTOCOLS": "raw,ssh",
        },
        "volumes": [
            f"./{DATA_DIR}:/data",
        ],
        "healthcheck": {
            "test": ["CMD", "sh", "-c", f"nc -z localhost {DEFAULT_QUERY_PORT_RAW}"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
            "start_period": "15s",
        },
        "networks": [DOCKER_NETWORK],
    }


def _build_orchestrator_service(config: SetupConfig) -> dict[str, Any]:
    """Build the ``python-orchestrator`` service definition dict."""
    python_image = (
        IRAN_PYTHON_IMAGE if config.iran_mirrors else DEFAULT_PYTHON_IMAGE
    )
    pip_index = IRAN_PIP_INDEX if config.iran_mirrors else DEFAULT_PIP_INDEX

    return {
        "image": python_image,
        "container_name": "ts3-orchestrator",
        "restart": "unless-stopped",
        "depends_on": {
            "teamspeak": {"condition": "service_healthy"},
        },
        "environment": {
            "TS3_QUERY_HOST": "ts3-server",
            "TS3_QUERY_PORT": str(DEFAULT_QUERY_PORT_RAW),
            "TS3_QUERY_PASSWORD": config.query_password,
            "MELODIFY_API_KEY": config.melodify_api_key,
            "PIP_INDEX_URL": pip_index,
        },
        "volumes": [
            "./bot:/app:ro",
        ],
        "working_dir": "/app",
        "command": [
            "sh",
            "-c",
            "pip install --quiet -r requirements.txt && python melodify_ts_bot/main.py",
        ],
        "networks": [DOCKER_NETWORK],
    }


def _build_audiobot_service(config: SetupConfig) -> dict[str, Any]:
    """Build the ``ts3audiobot`` service definition dict."""
    audiobot_image = (
        IRAN_AUDIOBOT_IMAGE if config.iran_mirrors else DEFAULT_AUDIOBOT_IMAGE
    )

    return {
        "image": audiobot_image,
        "container_name": "ts3-audiobot",
        "restart": "unless-stopped",
        "depends_on": {
            "teamspeak": {"condition": "service_healthy"},
        },
        "environment": {
            "TS3_HOST": "ts3-server",
        },
        "volumes": [
            "./audiobot-data:/app/data",
        ],
        "networks": [DOCKER_NETWORK],
    }


def _yaml_dump_minimal(data: dict[str, Any], indent: int = 0) -> str:
    """Produce a *good-enough* YAML serialisation without PyYAML.

    This handles the subset of types that docker-compose files actually
    use: strings, ints, bools, lists (of strings/dicts), and nested dicts.
    The output is deterministic and human-readable.
    """
    lines: list[str] = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_yaml_dump_minimal(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    # Inline dict under a list item (e.g. healthcheck test).
                    first = True
                    for k, v in item.items():
                        if first:
                            lines.append(f"{prefix}  - {k}: {_yaml_scalar(v)}")
                            first = False
                        else:
                            lines.append(f"{prefix}    {k}: {_yaml_scalar(v)}")
                else:
                    lines.append(f"{prefix}  - {_yaml_scalar(item)}")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")

    return "\n".join(lines)


def _yaml_scalar(value: Any) -> str:
    """Convert a scalar value to its YAML representation."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # Quote strings that contain special YAML characters or look numeric.
        needs_quoting = any(
            c in value for c in (":", "{", "}", "[", "]", ",", "&", "*", "#",
                                  "?", "|", "-", "<", ">", "=", "!", "%",
                                  "@", "`", "'", '"')
        )
        if needs_quoting:
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        return value
    return str(value)


def generate_docker_compose(config: SetupConfig) -> str:
    """Generate ``docker-compose.yml`` content.

    Args:
        config: Fully populated ``SetupConfig``.

    Returns:
        The YAML content as a string.
    """
    services: dict[str, Any] = {
        "teamspeak": _build_teamspeak_service(config),
    }

    if config.music_bot_enabled:
        services["ts3audiobot"] = _build_audiobot_service(config)
        services["python-orchestrator"] = _build_orchestrator_service(config)

    compose: dict[str, Any] = {
        "services": {},
        "networks": {
            DOCKER_NETWORK: {
                "driver": "bridge",
            },
        },
    }

    # Build the YAML manually to keep ordering and readability.
    header = textwrap.dedent("""\
        # ── tschan – auto-generated docker-compose.yml ───────────────────────
        #
        # Do not edit manually — re-run tschan to regenerate.
        #
    """)

    body_lines: list[str] = ["services:"]
    for svc_name, svc_def in services.items():
        body_lines.append(f"  {svc_name}:")
        body_lines.append(_yaml_dump_minimal(svc_def, indent=2))
        body_lines.append("")

    body_lines.append("networks:")
    body_lines.append(_yaml_dump_minimal(compose["networks"], indent=1))
    body_lines.append("")

    return header + "\n".join(body_lines)


# ── Disk I/O ─────────────────────────────────────────────────────────────────


def write_all(config: SetupConfig, project_dir: Path) -> None:
    """Write every generated file to disk.

    Creates the following under *project_dir*:

    - ``.env``
    - ``docker-compose.yml``
    - ``ts3-data/`` directory
    - ``ts3-data/query_ip_allowlist.txt``
    - ``ts3-data/query_ip_denylist.txt`` (empty)
    - ``.tschan.json`` (serialised ``SetupConfig``)

    Args:
        config: Fully populated and validated ``SetupConfig``.
        project_dir: Root directory of the deployment.

    Raises:
        OSError: If any file/directory operation fails.
    """
    project_dir = Path(project_dir)
    data_dir = project_dir / DATA_DIR

    # Ensure directories exist.
    project_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # .env
    env_path = project_dir / ENV_FILE
    env_path.write_text(generate_env(config), encoding="utf-8")

    # docker-compose.yml
    compose_path = project_dir / COMPOSE_FILE
    compose_path.write_text(generate_docker_compose(config), encoding="utf-8")

    # query_ip_allowlist.txt
    allowlist_path = data_dir / "query_ip_allowlist.txt"
    allowlist_path.write_text(QUERY_IP_ALLOWLIST, encoding="utf-8")

    # query_ip_denylist.txt (empty)
    denylist_path = data_dir / "query_ip_denylist.txt"
    if not denylist_path.exists():
        denylist_path.write_text("", encoding="utf-8")

    # .tschan.json
    state_path = project_dir / STATE_FILE
    state_path.write_text(config.to_json(), encoding="utf-8")


def load_config(project_dir: Path) -> SetupConfig | None:
    """Load a previously saved ``SetupConfig`` from ``.tschan.json``.

    Args:
        project_dir: Root directory of the deployment.

    Returns:
        The deserialized ``SetupConfig``, or ``None`` if the state file
        does not exist.

    Raises:
        json.JSONDecodeError: If the file exists but contains invalid JSON.
    """
    state_path = Path(project_dir) / STATE_FILE
    if not state_path.is_file():
        return None
    text = state_path.read_text(encoding="utf-8")
    return SetupConfig.from_json(text)
