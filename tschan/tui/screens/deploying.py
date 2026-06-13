"""Deployment progress screen — writes config, starts Docker, sets up TS3."""

from __future__ import annotations

import time
import traceback
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, ProgressBar, RichLog, Static

from tschan.constants import DEFAULT_QUERY_PORT_RAW
from tschan.models import SetupConfig

# ── Deployment Steps ─────────────────────────────────────────────────────────

DEPLOY_STEPS: list[str] = [
    "Writing configuration files...",
    "Creating server data directory...",
    "Starting Docker containers...",
    "Waiting for TeamSpeak server to start...",
    "Configuring server channels and roles...",
    "Generating your privilege key...",
    "Deployment complete.",
]

DEPLOY_LOG_FILE = "tschan-deploy.log"


class DeployingScreen(Screen):
    """Shows deployment progress with a worker-driven pipeline."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, config: SetupConfig, project_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.privilege_key: str = ""
        self._active_step_index: int | None = None
        self._failed = False
        self._log_path = self.project_dir / DEPLOY_LOG_FILE

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Deploying Your Server", classes="step-title")
        yield Static(
            "[#8b949e]Keep this window open until deployment finishes.[/]",
            classes="step-subtitle",
        )

        with VerticalScroll(classes="deploy-container"):
            yield ProgressBar(
                total=len(DEPLOY_STEPS),
                id="deploy-progress",
            )
            yield Static(
                "[#8b949e]Preparing deployment...[/]",
                id="deploy-status",
                classes="deploy-status",
            )
            # One Static per step for status display
            for i, step_text in enumerate(DEPLOY_STEPS):
                yield Static(
                    f"  ○  {step_text}",
                    id=f"deploy-step-{i}",
                    classes="deploy-step",
                )
            yield Static("", id="deploy-error", classes="error-text")
            yield Static(
                f"Deployment log: {self._log_path}",
                classes="deploy-log-path",
            )
            yield RichLog(
                id="deploy-log",
                classes="deploy-log",
                highlight=False,
                markup=True,
                wrap=True,
            )

        yield Footer()

    def on_mount(self) -> None:
        """Start the deployment worker."""
        self._prepare_log_file()
        self._append_log_line("Deployment screen mounted.")
        self._append_log_line("Starting deployment worker.")
        self._set_step_active(0)
        self._run_deployment()

    def _prepare_log_file(self) -> None:
        """Create the project directory and reset the deploy debug log."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._log_path.write_text(
            "tschan deployment log\n"
            f"project_dir={self.project_dir}\n"
            "----------------------------------------\n",
            encoding="utf-8",
        )

    def _write_log_line(self, line: str) -> None:
        """Append a line to the persistent deployment log."""
        try:
            with self._log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    def _append_log_line(self, message: str) -> None:
        """Append a line to the visible log and persistent log."""
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        self._write_log_line(line)
        try:
            self.query_one("#deploy-log", RichLog).write(line)
        except Exception:
            pass

    def _log_from_worker(self, message: str) -> None:
        """Log from the deployment worker thread."""
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        self._write_log_line(line)
        self.call_from_thread(self._append_log_ui_only, line)

    def _append_log_ui_only(self, line: str) -> None:
        """Append a preformatted line to the visible log only."""
        try:
            self.query_one("#deploy-log", RichLog).write(line)
        except Exception:
            pass

    def _log_docker_output(self, raw_line: str) -> None:
        """Stream Docker output into the deployment log."""
        line = raw_line.strip()
        if line:
            self._log_from_worker(f"docker: {line}")

    def _set_step_state(self, index: int, state: str) -> None:
        """Mark a step as pending, done, active, or error."""
        step_widget = self.query_one(f"#deploy-step-{index}", Static)
        text = DEPLOY_STEPS[index]
        if state == "done":
            step_widget.update(f"  [#3fb950]✓[/]  [#3fb950]{text}[/]")
            step_widget.add_class("--done")
            step_widget.remove_class("--active", "--error")
        elif state == "active":
            self._active_step_index = index
            step_widget.update(f"  [bold #f0f6fc]●[/]  [bold #f0f6fc]{text}[/]")
            step_widget.add_class("--active")
            step_widget.remove_class("--done", "--error")
        elif state == "error":
            step_widget.update(f"  [#f85149]✗[/]  [#f85149]{text}[/]")
            step_widget.add_class("--error")
            step_widget.remove_class("--done", "--active")

    def _set_step_active(self, index: int) -> None:
        """Show the active deployment step."""
        self._set_step_state(index, "active")
        self.query_one("#deploy-status", Static).update(
            f"[#f0f6fc]{DEPLOY_STEPS[index]}[/]"
        )
        self._append_log_line(f"Step {index + 1}/{len(DEPLOY_STEPS)} started: {DEPLOY_STEPS[index]}")

    def _set_step_done(self, index: int) -> None:
        """Mark a deployment step complete and advance progress."""
        self._set_step_state(index, "done")
        progress = self.query_one("#deploy-progress", ProgressBar)
        progress.update(progress=index + 1)
        self.query_one("#deploy-status", Static).update(
            f"[#3fb950]Completed {index + 1} of {len(DEPLOY_STEPS)} steps[/]"
        )
        self._append_log_line(f"Step {index + 1}/{len(DEPLOY_STEPS)} completed: {DEPLOY_STEPS[index]}")

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _run_deployment(self) -> None:
        """Execute the full deployment pipeline in a background thread."""
        project_dir = self.project_dir
        config = self.config

        try:
            self._log_from_worker("Deployment worker is running.")
            self._log_from_worker(f"Project directory: {project_dir}")
            # Step 0: Write configuration files
            self.call_from_thread(self._set_step_active, 0)
            from tschan.engine.config_writer import write_all

            self._log_from_worker("Writing .env, docker-compose.yml, state, and TS3 data files.")
            write_all(config, project_dir)
            time.sleep(0.3)
            self.call_from_thread(self._set_step_done, 0)

            # Step 1: Create data directory
            self.call_from_thread(self._set_step_active, 1)
            data_dir = project_dir / "ts3-data"
            self._log_from_worker(f"Ensuring data directory exists: {data_dir}")
            data_dir.mkdir(exist_ok=True)
            time.sleep(0.2)
            self.call_from_thread(self._set_step_done, 1)

            # Step 2: Start Docker containers
            self.call_from_thread(self._set_step_active, 2)
            from tschan.engine.docker_ctl import DockerController

            docker = DockerController(project_dir)
            self._log_from_worker("Running: docker compose up -d --build")
            self._log_from_worker("Docker image pulls/builds can take several minutes on first run.")
            docker.compose_up(build=True, on_output=self._log_docker_output)
            self._log_from_worker("Docker compose up finished successfully.")
            self.call_from_thread(self._set_step_done, 2)

            # Step 3: Wait for TS3 to be ready
            self.call_from_thread(self._set_step_active, 3)
            self._log_from_worker("Waiting for TeamSpeak ServerQuery login to succeed.")
            self._wait_for_ts3(docker)
            self._log_from_worker("TeamSpeak ServerQuery is ready.")
            self.call_from_thread(self._set_step_done, 3)

            # Step 4: Configure server
            self.call_from_thread(self._set_step_active, 4)
            from tschan.engine.ts3_query import TS3QueryClient

            self._log_from_worker("Connecting to ServerQuery for channel and role setup.")
            client = TS3QueryClient(
                host="127.0.0.1",
                port=DEFAULT_QUERY_PORT_RAW,
                username="serveradmin",
                password=config.query_password,
            )
            client.connect()
            privilege_key = client.setup_server(config)
            client.disconnect()
            self._log_from_worker("Server channels, roles, and metadata configured.")
            self.call_from_thread(self._set_step_done, 4)

            # Step 5: Generate privilege key
            self.call_from_thread(self._set_step_active, 5)
            self.privilege_key = privilege_key
            self._log_from_worker("Privilege key generated.")
            time.sleep(0.3)
            self.call_from_thread(self._set_step_done, 5)

            # Step 6: Complete!
            self.call_from_thread(self._set_step_active, 6)
            self._log_from_worker("Deployment completed successfully.")
            self.call_from_thread(self._set_step_done, 6)
            time.sleep(0.5)

            # Navigate to privilege key screen
            self.call_from_thread(self._show_privilege_key)

        except Exception as exc:
            error_msg = str(exc)
            self._log_from_worker(f"Deployment failed: {type(exc).__name__}: {error_msg}")
            for line in traceback.format_exc().splitlines():
                self._log_from_worker(line)
            self.call_from_thread(self._show_error, error_msg)

    def _wait_for_ts3(self, docker: object) -> None:
        """Poll until ServerQuery accepts login and server selection."""
        from tschan.engine.docker_ctl import DockerController
        from tschan.engine.ts3_query import TS3QueryClient

        assert isinstance(docker, DockerController)
        for attempt in range(1, 31):
            client: TS3QueryClient | None = None
            try:
                if docker.is_running():
                    self._log_from_worker(
                        f"ServerQuery readiness check {attempt}/30: container is running."
                    )
                    client = TS3QueryClient(
                        host="127.0.0.1",
                        port=DEFAULT_QUERY_PORT_RAW,
                        username="serveradmin",
                        password=self.config.query_password,
                    )
                    client.connect(timeout=2.0)
                    client.login()
                    client.use_server(1)
                    return
                self._log_from_worker(
                    f"ServerQuery readiness check {attempt}/30: container not running yet."
                )
            except Exception as exc:
                self._log_from_worker(
                    f"ServerQuery readiness check {attempt}/30 failed: "
                    f"{type(exc).__name__}: {exc}"
                )
            finally:
                if client is not None:
                    client.disconnect()
            time.sleep(2)
        raise TimeoutError(
            "TeamSpeak ServerQuery did not become ready within 60 seconds"
        )

    def _show_privilege_key(self) -> None:
        """Navigate to the privilege key screen."""
        from tschan.tui.screens.privilege_key import PrivilegeKeyScreen

        self.app.push_screen(
            PrivilegeKeyScreen(
                self.privilege_key,
                self.project_dir,
                self.config.server_name,
            )
        )

    def _show_error(self, error_msg: str) -> None:
        """Display the error message on screen."""
        self._failed = True
        if self._active_step_index is not None:
            self._set_step_state(self._active_step_index, "error")
        self.query_one("#deploy-status", Static).update(
            "[#f85149]Deployment failed[/]"
        )
        self._append_log_line(f"Deployment failed. See {self._log_path}")
        error_widget = self.query_one("#deploy-error", Static)
        error_widget.update(
            f"[bold #f85149]Deployment failed:[/]\n"
            f"[#f85149]{error_msg}[/]\n\n"
            f"[#8b949e]Press Escape to go back and try again.[/]"
        )

    def action_go_back(self) -> None:
        """Go back after an error; ignore Escape during active deployment."""
        if self._failed:
            self.app.pop_screen()
