"""Deployment progress screen — writes config, starts Docker, sets up TS3."""

from __future__ import annotations

import time
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, ProgressBar, Static

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

        yield Footer()

    def on_mount(self) -> None:
        """Start the deployment worker."""
        self._run_deployment()

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

    def _set_step_done(self, index: int) -> None:
        """Mark a deployment step complete and advance progress."""
        self._set_step_state(index, "done")
        progress = self.query_one("#deploy-progress", ProgressBar)
        progress.update(progress=index + 1)
        self.query_one("#deploy-status", Static).update(
            f"[#3fb950]Completed {index + 1} of {len(DEPLOY_STEPS)} steps[/]"
        )

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _run_deployment(self) -> None:
        """Execute the full deployment pipeline in a background thread."""
        project_dir = self.project_dir
        config = self.config

        try:
            # Step 0: Write configuration files
            self.call_from_thread(self._set_step_active, 0)
            from tschan.engine.config_writer import write_all

            write_all(config, project_dir)
            time.sleep(0.3)
            self.call_from_thread(self._set_step_done, 0)

            # Step 1: Create data directory
            self.call_from_thread(self._set_step_active, 1)
            data_dir = project_dir / "ts3-data"
            data_dir.mkdir(exist_ok=True)
            time.sleep(0.2)
            self.call_from_thread(self._set_step_done, 1)

            # Step 2: Start Docker containers
            self.call_from_thread(self._set_step_active, 2)
            from tschan.engine.docker_ctl import DockerController

            docker = DockerController(project_dir)
            docker.compose_up(build=True)
            self.call_from_thread(self._set_step_done, 2)

            # Step 3: Wait for TS3 to be ready
            self.call_from_thread(self._set_step_active, 3)
            self._wait_for_ts3(docker)
            self.call_from_thread(self._set_step_done, 3)

            # Step 4: Configure server
            self.call_from_thread(self._set_step_active, 4)
            from tschan.engine.ts3_query import TS3QueryClient

            client = TS3QueryClient(
                host="127.0.0.1",
                port=DEFAULT_QUERY_PORT_RAW,
                username="serveradmin",
                password=config.query_password,
            )
            client.connect()
            privilege_key = client.setup_server(config)
            client.disconnect()
            self.call_from_thread(self._set_step_done, 4)

            # Step 5: Generate privilege key
            self.call_from_thread(self._set_step_active, 5)
            self.privilege_key = privilege_key
            time.sleep(0.3)
            self.call_from_thread(self._set_step_done, 5)

            # Step 6: Complete!
            self.call_from_thread(self._set_step_active, 6)
            self.call_from_thread(self._set_step_done, 6)
            time.sleep(0.5)

            # Navigate to privilege key screen
            self.call_from_thread(self._show_privilege_key)

        except Exception as exc:
            error_msg = str(exc)
            self.call_from_thread(self._show_error, error_msg)

    def _wait_for_ts3(self, docker: object) -> None:
        """Poll until ServerQuery accepts login and server selection."""
        from tschan.engine.docker_ctl import DockerController
        from tschan.engine.ts3_query import TS3QueryClient

        assert isinstance(docker, DockerController)
        for _ in range(30):
            client: TS3QueryClient | None = None
            try:
                if docker.is_running():
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
            except Exception:
                pass
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
