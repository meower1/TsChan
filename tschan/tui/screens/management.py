"""Post-deployment management panel screen."""

from __future__ import annotations

import shutil
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Button, Header, Label, RichLog, Static

from tschan.constants import DATA_DIR, ENV_FILE, STATE_FILE, DEFAULT_QUERY_PORT_RAW
from tschan.models import SetupConfig


class ConfirmUninstallScreen(Screen):
    """Modal confirmation dialog for uninstall."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="confirm-dialog"):
            with Vertical(classes="confirm-box"):
                yield Static(
                    "[bold #fb7185]Uninstall Server[/]",
                    classes="confirm-title",
                )
                yield Static(
                    "[#c9d1d9]Are you sure? This will:[/]\n\n"
                    "  [#fb7185]•[/] Stop all Docker containers\n"
                    "  [#fb7185]•[/] Delete ALL server data\n"
                    "  [#fb7185]•[/] Remove configuration files\n\n"
                    "[bold #fb7185]This action cannot be undone.[/]",
                    classes="confirm-message",
                )
                with Horizontal(classes="confirm-buttons"):
                    yield Button(
                        "Cancel",
                        id="btn-cancel-uninstall",
                        variant="primary",
                    )
                    yield Button(
                        "Yes, Uninstall",
                        id="btn-confirm-uninstall",
                        variant="error",
                    )

    @on(Button.Pressed, "#btn-cancel-uninstall")
    def _on_cancel(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-confirm-uninstall")
    def _on_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.app.pop_screen()


class ManagementScreen(Screen):
    """Post-deployment management panel with server controls and log viewer."""

    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("r", "refresh_status", "Refresh"),
    ]

    def __init__(self, config: SetupConfig, project_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.project_dir = Path(project_dir).expanduser().resolve()
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        yield Static(
            "[bold #e2e8f0]tschan Management[/]",
            classes="step-title",
        )

        with VerticalScroll():
            # ── Status Bar ───────────────────────────────────────
            with Vertical(classes="status-bar"):
                yield Static(
                    "",
                    id="status-server-name",
                    classes="status-label",
                )
                yield Static(
                    "",
                    id="status-running",
                )
                yield Static(
                    "",
                    id="status-clients",
                    classes="muted-text",
                )

            # ── Action Buttons ───────────────────────────────────────
            with Horizontal(classes="management-primary"):
                yield Button(
                    "Start",
                    id="btn-start",
                    variant="success",
                )
                yield Button(
                    "Stop",
                    id="btn-stop",
                    variant="error",
                )
                yield Button(
                    "Restart",
                    id="btn-restart",
                    variant="warning",
                )

            with Horizontal(classes="management-secondary"):
                yield Button(
                    "Refresh",
                    id="btn-refresh",
                    variant="default",
                )
                yield Button(
                    "Logs",
                    id="btn-logs",
                    variant="default",
                )
                yield Button(
                    "New Key",
                    id="btn-key",
                    variant="default",
                )
                yield Button(
                    "Uninstall",
                    id="btn-uninstall",
                    variant="error",
                )
                yield Button(
                    "Exit",
                    id="btn-exit",
                    variant="default",
                )

            # ── Log Viewer ───────────────────────────────────────
            yield RichLog(
                id="log-viewer",
                classes="log-viewer",
                highlight=True,
                markup=True,
            )


    def on_mount(self) -> None:
        """Initialize the status display and start auto-refresh."""
        self._update_server_name()
        self._refresh_status()
        self._refresh_timer = self.set_interval(5.0, self._refresh_status)

    def on_unmount(self) -> None:
        """Stop the auto-refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.stop()

    # ── Status Updates ───────────────────────────────────────────────────────

    def _update_server_name(self) -> None:
        """Display the server name in the status bar."""
        name_widget = self.query_one("#status-server-name", Static)
        name_widget.update(
            f"[bold #e2e8f0]Server:[/] [#c9d1d9]{self.config.server_name}[/]\n"
            f"[bold #e2e8f0]Project:[/] [#6e7681]{self.project_dir}[/]"
        )

    @work(thread=True, exclusive=True, group="status")
    def _refresh_status(self) -> None:
        """Refresh the server status from Docker (runs in a thread)."""
        try:
            from tschan.engine.docker_ctl import DockerController

            docker = DockerController(self.project_dir)
            is_running = docker.is_running()
            containers = docker.get_containers()

            if is_running:
                status_text = "[bold #34d399]● Running[/]"
                container_info = "  ".join(
                    f"[#6e7681]{c.name}:[/] [#34d399]{c.status}[/]"
                    for c in containers
                )
            else:
                status_text = "[bold #fb7185]● Stopped[/]"
                container_info = "[#6e7681]No containers running[/]"

            self.app.call_from_thread(
                self._set_status, status_text, container_info
            )

            # Try to get client count if running
            if is_running:
                try:
                    from tschan.engine.ts3_query import TS3QueryClient

                    client = TS3QueryClient(
                        host="127.0.0.1",
                        port=DEFAULT_QUERY_PORT_RAW,
                        username="serveradmin",
                        password=self.config.query_password,
                    )
                    client.connect()
                    info = client.get_server_info()
                    client.disconnect()
                    self.app.call_from_thread(
                        self._set_clients,
                        f"[#6e7681]Clients:[/] [#e2e8f0]{info.clients_online}"
                        f"/{info.max_clients}[/]  ·  "
                        f"[#6e7681]Uptime:[/] [#e2e8f0]"
                        f"{info.uptime_seconds // 3600}h "
                        f"{(info.uptime_seconds % 3600) // 60}m[/]",
                    )
                except Exception:
                    self.app.call_from_thread(
                        self._set_clients,
                        "[#6e7681]Could not query server info[/]",
                    )
        except Exception as exc:
            self.app.call_from_thread(
                self._set_status,
                "[bold #fb7185]● Error[/]",
                f"[#fb7185]{exc}[/]",
            )

    def _set_status(self, status_text: str, container_info: str) -> None:
        """Update status widgets on the main thread."""
        self.query_one("#status-running", Static).update(status_text)
        self.query_one("#status-clients", Static).update(container_info)

    def _set_clients(self, text: str) -> None:
        """Update client info on the main thread."""
        self.query_one("#status-clients", Static).update(text)

    # ── Button Handlers ──────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-start")
    def _on_start(self) -> None:
        self._docker_action("start")

    @on(Button.Pressed, "#btn-stop")
    def _on_stop(self) -> None:
        self._docker_action("stop")

    @on(Button.Pressed, "#btn-restart")
    def _on_restart(self) -> None:
        self._docker_action("restart")

    @on(Button.Pressed, "#btn-refresh")
    def _on_refresh(self) -> None:
        self.action_refresh_status()

    @on(Button.Pressed, "#btn-logs")
    def _on_logs(self) -> None:
        self.action_toggle_logs()

    @on(Button.Pressed, "#btn-key")
    def _on_generate_key(self) -> None:
        self._generate_privilege_key()

    @on(Button.Pressed, "#btn-uninstall")
    def _on_uninstall(self) -> None:
        self._confirm_uninstall()

    @on(Button.Pressed, "#btn-exit")
    def _on_exit(self) -> None:
        self.app.exit()

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_refresh_status(self) -> None:
        self._refresh_status()
        self.notify("Refreshing status...", title="Status")

    def action_toggle_logs(self) -> None:
        """Toggle log viewer visibility and fetch logs."""
        log_viewer = self.query_one("#log-viewer", RichLog)
        if log_viewer.has_class("--visible"):
            log_viewer.remove_class("--visible")
        else:
            log_viewer.add_class("--visible")
            self._fetch_logs()

    # ── Worker Tasks ─────────────────────────────────────────────────────────

    @work(thread=True, exclusive=True, group="docker-action")
    def _docker_action(self, action: str) -> None:
        """Execute a Docker action in a background thread."""
        try:
            from tschan.engine.docker_ctl import DockerController

            docker = DockerController(self.project_dir)

            if action == "start":
                self.app.call_from_thread(
                    self.notify, "Starting server...", title="Start"
                )
                docker.compose_up(build=False)
                self.app.call_from_thread(
                    self.notify,
                    "Server started.",
                    title="Done",
                    severity="information",
                )
            elif action == "stop":
                self.app.call_from_thread(
                    self.notify, "Stopping server...", title="Stop"
                )
                docker.compose_down(volumes=False)
                self.app.call_from_thread(
                    self.notify,
                    "Server stopped.",
                    title="Done",
                    severity="information",
                )
            elif action == "restart":
                self.app.call_from_thread(
                    self.notify, "Restarting server...", title="Restart"
                )
                docker.compose_restart()
                self.app.call_from_thread(
                    self.notify,
                    "Server restarted.",
                    title="Done",
                    severity="information",
                )

            # Refresh status after action
            self.app.call_from_thread(self._refresh_status)

        except Exception as exc:
            self.app.call_from_thread(
                self.notify,
                f"Docker error: {exc}",
                title="Error",
                severity="error",
            )

    @work(thread=True, exclusive=True, group="logs")
    def _fetch_logs(self) -> None:
        """Fetch docker compose logs in a background thread."""
        try:
            from tschan.engine.docker_ctl import DockerController

            docker = DockerController(self.project_dir)
            logs = docker.compose_logs(tail=100)
            self.app.call_from_thread(self._display_logs, logs)
        except Exception as exc:
            self.app.call_from_thread(
                self._display_logs,
                f"Error fetching logs: {exc}",
            )

    def _display_logs(self, logs: str) -> None:
        """Display logs in the RichLog widget."""
        log_viewer = self.query_one("#log-viewer", RichLog)
        log_viewer.clear()
        for line in logs.split("\n"):
            log_viewer.write(line)

    @work(thread=True, exclusive=True, group="keygen")
    def _generate_privilege_key(self) -> None:
        """Generate a new privilege key."""
        try:
            from tschan.engine.ts3_query import TS3QueryClient

            self.app.call_from_thread(
                self.notify, "Generating privilege key...", title="Privilege key"
            )

            client = TS3QueryClient(
                host="127.0.0.1",
                port=DEFAULT_QUERY_PORT_RAW,
                username="serveradmin",
                password=self.config.query_password,
            )
            client.connect()
            key = client.generate_privilege_key(group_name="Dev")
            client.disconnect()

            self.app.call_from_thread(self._show_new_key, key)

        except Exception as exc:
            self.app.call_from_thread(
                self.notify,
                f"Failed to generate key: {exc}",
                title="Error",
                severity="error",
            )

    def _show_new_key(self, key: str) -> None:
        """Show the new privilege key in a popup screen."""
        from tschan.tui.screens.privilege_key import PrivilegeKeyScreen

        self.app.push_screen(
            PrivilegeKeyScreen(key, self.project_dir, self.config.server_name)
        )

    def _confirm_uninstall(self) -> None:
        """Show the uninstall confirmation dialog."""

        def on_dismiss(result: bool | None) -> None:
            if result:
                self._do_uninstall()

        self.app.push_screen(ConfirmUninstallScreen(), callback=on_dismiss)

    @work(thread=True, exclusive=True, group="uninstall")
    def _do_uninstall(self) -> None:
        """Perform the actual uninstall."""
        try:
            self.app.call_from_thread(
                self.notify, "Uninstalling server...", title="Uninstall"
            )

            project_dir = self.project_dir

            # Stop containers and remove volumes
            from tschan.engine.docker_ctl import DockerController

            docker = DockerController(project_dir)
            try:
                docker.compose_down(volumes=True)
            except Exception:
                pass  # containers might not exist

            # Remove data directory
            data_path = project_dir / DATA_DIR
            if data_path.exists():
                shutil.rmtree(data_path)

            # Remove config files
            for fname in (STATE_FILE, ENV_FILE):
                fpath = project_dir / fname
                if fpath.exists():
                    fpath.unlink()

            self.app.call_from_thread(
                self.notify,
                "Server uninstalled successfully.",
                title="Done",
                severity="information",
            )

            # Exit after a brief pause
            import time

            time.sleep(1.5)
            self.app.call_from_thread(self.app.exit)

        except Exception as exc:
            self.app.call_from_thread(
                self.notify,
                f"Uninstall error: {exc}",
                title="Error",
                severity="error",
            )
