"""Raw TCP ServerQuery client for TeamSpeak 3.

Connects to the TS3 ServerQuery interface on port 10011 and provides
high-level methods for server setup, channel/group creation, and
privilege key generation.

Public API
----------
- ``TS3QueryClient`` — the main client class.
"""

from __future__ import annotations

import logging
import re
import socket
import time
from typing import Any

from tschan.constants import (
    DEFAULT_QUERY_PORT_RAW,
    TEMPLATE_SERVER_NAME_SUFFIX,
)
from tschan.models import ServerInfo, SetupConfig
from tschan.templates.channels import get_template
from tschan.templates.roles import get_roles_for_groups

LOGGER = logging.getLogger(__name__)

# ── TS3 ServerQuery string escaping ──────────────────────────────────────────

_ESCAPE_MAP = [
    ("\\", "\\\\"),   # backslash MUST be first
    ("/", "\\/"),
    (" ", "\\s"),
    ("|", "\\p"),
    ("\n", "\\n"),
    ("\r", "\\r"),
    ("\t", "\\t"),
]

# For unescaping, we map the TS3 escape codes back to their characters.
# We use a dict keyed by the character after the backslash.
_UNESCAPE_CHARS: dict[str, str] = {
    "\\": "\\",
    "/": "/",
    "s": " ",
    "p": "|",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "v": "\v",
}


class TS3QueryError(Exception):
    """Raised when a ServerQuery command fails."""

    def __init__(self, message: str, error_id: int = -1):
        super().__init__(message)
        self.error_id = error_id


class TS3QueryClient:
    """Raw TCP client for TeamSpeak 3 ServerQuery (port 10011).

    Usage::

        client = TS3QueryClient(host="127.0.0.1", password="secret")
        client.connect()
        try:
            key = client.setup_server(config)
            print(f"Privilege key: {key}")
        finally:
            client.disconnect()

    Args:
        host: TS3 server hostname or IP.
        port: ServerQuery raw port (default 10011).
        username: ServerQuery username (default ``serveradmin``).
        password: ServerQuery password.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = DEFAULT_QUERY_PORT_RAW,
        username: str = "serveradmin",
        password: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._sock: socket.socket | None = None

    # ── Connection lifecycle ─────────────────────────────────────────────

    def connect(self, timeout: float = 10.0) -> None:
        """Open a TCP connection and read the welcome banner.

        Raises:
            ConnectionError: If the connection fails.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        try:
            self._sock.connect((self.host, self.port))
        except (socket.error, OSError) as exc:
            self._sock = None
            raise ConnectionError(
                f"Failed to connect to {self.host}:{self.port}: {exc}"
            ) from exc

        # Read and discard the TS3 welcome banner (two lines).
        self._recv()
        LOGGER.debug("Connected to ServerQuery at %s:%d", self.host, self.port)

    def disconnect(self) -> None:
        """Gracefully close the connection."""
        if self._sock is not None:
            try:
                self._send("quit")
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
            LOGGER.debug("Disconnected from ServerQuery")

    # ── Low-level I/O ────────────────────────────────────────────────────

    def _send(self, command: str) -> None:
        """Send a raw command string (newline-terminated)."""
        if self._sock is None:
            raise TS3QueryError("Not connected")
        self._sock.sendall((command + "\n").encode("utf-8"))

    def _recv(self, max_bytes: int = 65536) -> str:
        """Read from the socket until we see the ``error`` response line.

        TS3 ServerQuery terminates every response with a line starting with
        ``error id=...``. We accumulate data until we see that sentinel.
        """
        if self._sock is None:
            raise TS3QueryError("Not connected")

        buf = b""
        while True:
            try:
                chunk = self._sock.recv(max_bytes)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            decoded = buf.decode("utf-8", errors="replace")
            # Check for the error terminator.
            if re.search(r"error id=\d+", decoded):
                return decoded
            # Also stop on the TS3 welcome banner.
            if "TS3\n" in decoded or "Welcome to" in decoded.lower():
                return decoded
        return buf.decode("utf-8", errors="replace")

    def send_command(self, cmd: str) -> str:
        """Send a command and return the raw response.

        Args:
            cmd: The full ServerQuery command string.

        Returns:
            The raw response text.

        Raises:
            TS3QueryError: If the server returns an error (id != 0).
        """
        LOGGER.debug(">>> %s", cmd)
        self._send(cmd)
        time.sleep(0.3)
        response = self._recv()
        LOGGER.debug("<<< %s", response.strip()[:200])

        # Parse the error line.
        error_match = re.search(
            r"error id=(\d+) msg=(\S+)", response
        )
        if error_match:
            error_id = int(error_match.group(1))
            error_msg = self.ts3_unescape(error_match.group(2))
            if error_id != 0:
                raise TS3QueryError(
                    f"ServerQuery error {error_id}: {error_msg}",
                    error_id=error_id,
                )
        return response

    # ── Auth & server selection ──────────────────────────────────────────

    def login(self) -> None:
        """Authenticate with the ServerQuery interface."""
        self.send_command(
            f"login {self.username} {self.ts3_escape(self.password)}"
        )
        LOGGER.info("Logged in as %s", self.username)

    def use_server(self, server_id: int = 1) -> None:
        """Select a virtual server."""
        self.send_command(f"use sid={server_id}")

    # ── High-level server setup ──────────────────────────────────────────

    def setup_server(self, config: SetupConfig) -> str:
        """Perform full server setup and return the privilege key.

        Steps:
            1. Login + select virtual server
            2. Set server name and welcome message
            3. Delete default channel
            4. Create all template channels
            5. Create all server groups
            6. Generate privilege key for Dev group

        Args:
            config: The validated setup configuration.

        Returns:
            The privilege key string.
        """
        self.login()
        self.use_server(1)

        # Set server name.
        suffix = TEMPLATE_SERVER_NAME_SUFFIX.get(
            config.template_name, "'s hangout"
        )
        full_name = f"{config.server_name}{suffix}"
        self.send_command(
            f"serveredit virtualserver_name={self.ts3_escape(full_name)}"
        )
        LOGGER.info("Server name set to: %s", full_name)

        # Set welcome message.
        if config.welcome_message:
            self.send_command(
                f"serveredit virtualserver_welcomemessage="
                f"{self.ts3_escape(config.welcome_message)}"
            )

        # Delete the default channel (id=1, "Default Channel").
        try:
            self.send_command("channeldelete cid=1 force=1")
            LOGGER.debug("Deleted default channel")
        except TS3QueryError:
            LOGGER.debug("Default channel already deleted or doesn't exist")

        # Create channels from template.
        channels = get_template(config.template_name)
        self.create_channels(channels)

        # Create server groups from role selections.
        roles = get_roles_for_groups(config.role_groups)
        self.create_server_groups(roles)

        # Generate privilege key.
        key = self.generate_privilege_key("Dev")
        LOGGER.info("Privilege key generated")
        return key

    def create_channels(self, channels: list[dict[str, Any]]) -> None:
        """Create channels from a template definition.

        Args:
            channels: List of channel descriptors from ``get_template()``.
        """
        prev_id = 0  # channel_order: place after the previously created channel
        for ch in channels:
            name = self.ts3_escape(ch["name"])
            cmd = (
                f"channelcreate channel_name={name} "
                f"channel_flag_permanent=1 "
                f"channel_order={prev_id} "
                f"channel_codec={ch.get('codec', 4)} "
                f"channel_codec_quality={ch.get('codec_quality', 6)}"
            )
            if ch.get("max_clients") is not None:
                cmd += f" channel_maxclients={ch['max_clients']}"
                cmd += " channel_flag_maxclients_unlimited=0"

            response = self.send_command(cmd)

            # Extract the created channel ID for ordering.
            cid_match = re.search(r"cid=(\d+)", response)
            if cid_match:
                prev_id = int(cid_match.group(1))
            LOGGER.debug("Created channel: %s", ch["name"])

    def create_server_groups(
        self, roles: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Create server groups from role definitions.

        Args:
            roles: List of role descriptors from ``get_roles_for_groups()``.

        Returns:
            Mapping of role name → server group ID.
        """
        group_map: dict[str, int] = {}
        for role in roles:
            name_escaped = self.ts3_escape(role["name"])
            try:
                response = self.send_command(
                    f"servergroupadd name={name_escaped}"
                )
                sgid_match = re.search(r"sgid=(\d+)", response)
                if sgid_match:
                    group_map[role["name"]] = int(sgid_match.group(1))
                    LOGGER.debug(
                        "Created group: %s (id=%s)",
                        role["name"],
                        sgid_match.group(1),
                    )
            except TS3QueryError as exc:
                if exc.error_id == 1282:  # group already exists
                    LOGGER.debug("Group already exists: %s", role["name"])
                else:
                    raise
        return group_map

    def generate_privilege_key(self, group_name: str = "Dev") -> str:
        """Generate a privilege key for the named server group.

        Args:
            group_name: Name of the server group to create a key for.

        Returns:
            The privilege key (token) string.

        Raises:
            TS3QueryError: If the group is not found or key creation fails.
        """
        # List all server groups.
        response = self.send_command("servergrouplist")

        # Parse groups to find the target.
        target_sgid: int | None = None
        for entry in response.split("|"):
            sgid_match = re.search(r"sgid=(\d+)", entry)
            name_match = re.search(r"name=(\S+)", entry)
            if sgid_match and name_match:
                name = self.ts3_unescape(name_match.group(1))
                if name == group_name:
                    target_sgid = int(sgid_match.group(1))
                    break

        if target_sgid is None:
            raise TS3QueryError(
                f"Server group '{group_name}' not found"
            )

        # Create the token.
        desc = self.ts3_escape(f"tschan auto-generated key for {group_name}")
        response = self.send_command(
            f"tokenadd tokentype=0 tokenid1={target_sgid} "
            f"tokenid2=0 tokendescription={desc}"
        )

        token_match = re.search(r"token=(\S+)", response)
        if not token_match:
            raise TS3QueryError(f"Failed to create privilege key: {response}")

        return token_match.group(1)

    # ── Server info ──────────────────────────────────────────────────────

    def get_server_info(self) -> ServerInfo:
        """Query live server information.

        Returns:
            ``ServerInfo`` with current server state.
        """
        self.login()
        self.use_server(1)
        response = self.send_command("serverinfo")

        def _extract(key: str, default: str = "") -> str:
            match = re.search(rf"{key}=(\S+)", response)
            return self.ts3_unescape(match.group(1)) if match else default

        return ServerInfo(
            name=_extract("virtualserver_name", "Unknown"),
            clients_online=int(_extract("virtualserver_clientsonline", "0")),
            max_clients=int(_extract("virtualserver_maxclients", "32")),
            uptime_seconds=int(_extract("virtualserver_uptime", "0")),
            version=_extract("virtualserver_version", "Unknown"),
            platform=_extract("virtualserver_platform", "Unknown"),
        )

    # ── Static helpers ───────────────────────────────────────────────────

    @staticmethod
    def ts3_escape(s: str) -> str:
        """Escape a string for TS3 ServerQuery protocol.

        Args:
            s: The raw string.

        Returns:
            The escaped string safe for ServerQuery commands.
        """
        for char, escaped in _ESCAPE_MAP:
            s = s.replace(char, escaped)
        return s

    @staticmethod
    def ts3_unescape(s: str) -> str:
        """Unescape a TS3 ServerQuery string.

        Args:
            s: The escaped string from ServerQuery.

        Returns:
            The unescaped human-readable string.
        """
        # Use regex to find all backslash-escaped sequences and replace them.
        def _replace(match: re.Match[str]) -> str:
            char = match.group(1)
            return _UNESCAPE_CHARS.get(char, "\\" + char)

        return re.sub(r"\\(.)", _replace, s)


def wait_for_query(
    host: str = "127.0.0.1",
    port: int = DEFAULT_QUERY_PORT_RAW,
    timeout: float = 60.0,
    interval: float = 2.0,
) -> bool:
    """Block until the TS3 ServerQuery port is accepting connections.

    Args:
        host: Target hostname.
        port: Target port.
        timeout: Maximum seconds to wait.
        interval: Seconds between retries.

    Returns:
        ``True`` if the port became reachable, ``False`` on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            # Read welcome banner to confirm it's TS3.
            data = sock.recv(256).decode("utf-8", errors="replace")
            sock.close()
            if "TS3" in data:
                return True
        except (socket.error, OSError):
            pass
        time.sleep(interval)
    return False
