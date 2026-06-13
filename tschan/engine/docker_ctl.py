"""Docker Compose wrapper for tschan.

Provides a high-level ``DockerController`` that shells out to
``docker compose`` (v2 CLI plugin syntax) to manage the TS3 stack.

Public API
----------
- ``DockerController(project_dir)`` — all compose operations scoped to a
  project directory.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from tschan.models import ContainerInfo


class DockerError(Exception):
    """Raised when a Docker Compose command fails."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class DockerController:
    """Manage a Docker Compose stack rooted at *project_dir*.

    All commands are run with the working directory set to *project_dir*
    so that ``docker compose`` automatically picks up the
    ``docker-compose.yml`` and ``.env`` files.

    Args:
        project_dir: Absolute or relative path to the project root.
    """

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = Path(project_dir).resolve()

    # ── Private helpers ──────────────────────────────────────────────────

    def _run(
        self,
        args: list[str],
        *,
        check: bool = True,
        capture: bool = True,
        timeout: int | None = 120,
    ) -> subprocess.CompletedProcess[str]:
        """Run a ``docker compose`` subcommand.

        Args:
            args: Arguments *after* ``docker compose`` (e.g. ``["up", "-d"]``).
            check: Raise on non-zero exit.
            capture: Capture stdout/stderr.
            timeout: Maximum seconds to wait.

        Returns:
            The ``CompletedProcess`` result.

        Raises:
            DockerError: On non-zero exit when *check* is True.
            FileNotFoundError: If ``docker`` is not on ``$PATH``.
        """
        cmd = ["docker", "compose", *args]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=capture,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise DockerError(
                "docker CLI not found – is Docker installed and on PATH?"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerError(
                f"Command timed out after {timeout}s: {' '.join(cmd)}"
            ) from exc

        if check and result.returncode != 0:
            raise DockerError(
                f"Command failed (exit {result.returncode}): {' '.join(cmd)}",
                returncode=result.returncode,
                stderr=result.stderr or "",
            )
        return result

    # ── Public compose operations ────────────────────────────────────────

    def compose_up(self, build: bool = True) -> subprocess.CompletedProcess[str]:
        """Start the stack in detached mode.

        Args:
            build: Pass ``--build`` to rebuild images.

        Returns:
            The completed process result.
        """
        args = ["up", "-d"]
        if build:
            args.append("--build")
        return self._run(args, timeout=300)

    def compose_down(self, volumes: bool = False) -> subprocess.CompletedProcess[str]:
        """Stop and remove the stack.

        Args:
            volumes: Also remove named volumes (``-v``).

        Returns:
            The completed process result.
        """
        args = ["down"]
        if volumes:
            args.append("-v")
        return self._run(args)

    def compose_restart(self) -> subprocess.CompletedProcess[str]:
        """Restart all services.

        Returns:
            The completed process result.
        """
        return self._run(["restart"])

    def compose_logs(self, tail: int = 100) -> str:
        """Fetch recent logs from all services.

        Args:
            tail: Number of trailing log lines to return.

        Returns:
            Combined stdout+stderr log output.
        """
        result = self._run(
            ["logs", "--tail", str(tail), "--no-color"],
            check=False,
        )
        return (result.stdout or "") + (result.stderr or "")

    def get_containers(self) -> list[ContainerInfo]:
        """List containers managed by this compose project.

        Parses ``docker compose ps --format json`` output. Each JSON object
        (or array of objects) is converted to a ``ContainerInfo``.

        Returns:
            List of ``ContainerInfo`` instances, possibly empty.
        """
        result = self._run(["ps", "--format", "json", "-a"], check=False)
        if not result.stdout or not result.stdout.strip():
            return []

        containers: list[ContainerInfo] = []
        raw = result.stdout.strip()

        # Docker Compose v2 may emit one JSON object per line *or* a
        # JSON array depending on version.  Handle both.
        parsed: list[dict[str, Any]]
        try:
            maybe = json.loads(raw)
            if isinstance(maybe, list):
                parsed = maybe
            else:
                parsed = [maybe]
        except json.JSONDecodeError:
            # One-object-per-line format.
            parsed = []
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    try:
                        parsed.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        for obj in parsed:
            containers.append(
                ContainerInfo(
                    name=obj.get("Name", obj.get("name", "unknown")),
                    state=obj.get("State", obj.get("state", "unknown")),
                    health=obj.get("Health", obj.get("health", "none")) or "none",
                    status=obj.get("Status", obj.get("status", "")),
                )
            )

        return containers

    def is_running(self) -> bool:
        """Return ``True`` if at least one container is in *running* state."""
        try:
            containers = self.get_containers()
        except DockerError:
            return False
        return any(c.state == "running" for c in containers)
