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
    "✨ Deployment complete!",
]


class DeployingScreen(Screen):
    """Shows deployment progress with a worker-driven pipeline."""

    BINDINGS = [
        ("escape", "noop", ""),
    ]

    def __init__(self, config: SetupConfig) -> None:
        super().__init__()
        self.config = config
        self.privilege_key: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "[bold #ff8fab]✦ ━━━  Deploying Your Server  ━━━ ✦[/]",
            classes="step-title",
        )
        yield Static(
            "[#9ca3af]Sit tight — this only takes a moment ✿[/]",
            classes="step-subtitle",
        )

        with VerticalScroll(classes="deploy-container"):
            yield ProgressBar(
                total=len(DEPLOY_STEPS),
                id="deploy-progress",
            )
            yield Static("", classes="sakura-divider")
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

    def _mark_step(self, index: int, state: str = "done") -> None:
        """Mark a step as done, active, or error."""
        step_widget = self.query_one(f"#deploy-step-{index}", Static)
        text = DEPLOY_STEPS[index]
        if state == "done":
            step_widget.update(f"  [#34d399]✓[/]  [#34d399]{text}[/]")
            step_widget.add_class("--done")
            step_widget.remove_class("--active", "--error")
        elif state == "active":
            step_widget.update(f"  [bold #ff8fab]●[/]  [bold #ff8fab]{text}[/]")
            step_widget.add_class("--active")
            step_widget.remove_class("--done", "--error")
        elif state == "error":
            step_widget.update(f"  [#f87171]✗[/]  [#f87171]{text}[/]")
            step_widget.add_class("--error")
            step_widget.remove_class("--done", "--active")

    def _advance_progress(self, step: int) -> None:
        """Update progress bar and mark the step as active."""
        progress = self.query_one("#deploy-progress", ProgressBar)
        progress.update(progress=step)
        if step < len(DEPLOY_STEPS):
            self._mark_step(step, "active")

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _run_deployment(self) -> None:
        """Execute the full deployment pipeline in a background thread."""
        project_dir = Path.cwd()
        config = self.config

        try:
            # Step 0: Write configuration files
            self.call_from_thread(self._advance_progress, 0)
            from tschan.engine.config_writer import write_all

            write_all(config, project_dir)
            time.sleep(0.3)
            self.call_from_thread(self._mark_step, 0, "done")

            # Step 1: Create data directory
            self.call_from_thread(self._advance_progress, 1)
            data_dir = project_dir / "ts3-data"
            data_dir.mkdir(exist_ok=True)
            time.sleep(0.2)
            self.call_from_thread(self._mark_step, 1, "done")

            # Step 2: Start Docker containers
            self.call_from_thread(self._advance_progress, 2)
            from tschan.engine.docker_ctl import DockerController

            docker = DockerController(project_dir)
            docker.compose_up(build=True)
            self.call_from_thread(self._mark_step, 2, "done")

            # Step 3: Wait for TS3 to be ready
            self.call_from_thread(self._advance_progress, 3)
            self._wait_for_ts3(docker)
            self.call_from_thread(self._mark_step, 3, "done")

            # Step 4: Configure server
            self.call_from_thread(self._advance_progress, 4)
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
            self.call_from_thread(self._mark_step, 4, "done")

            # Step 5: Generate privilege key
            self.call_from_thread(self._advance_progress, 5)
            self.privilege_key = privilege_key
            time.sleep(0.3)
            self.call_from_thread(self._mark_step, 5, "done")

            # Step 6: Complete!
            self.call_from_thread(self._advance_progress, 6)
            self.call_from_thread(self._mark_step, 6, "done")
            time.sleep(0.5)

            # Navigate to privilege key screen
            self.call_from_thread(self._show_privilege_key)

        except Exception as exc:
            error_msg = str(exc)
            self.call_from_thread(self._show_error, error_msg)

    def _wait_for_ts3(self, docker: object) -> None:
        """Poll until TS3 containers are running (max 60s)."""
        from tschan.engine.docker_ctl import DockerController

        assert isinstance(docker, DockerController)
        for _ in range(30):
            try:
                if docker.is_running():
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError(
            "TeamSpeak server did not start within 60 seconds"
        )

    def _show_privilege_key(self) -> None:
        """Navigate to the privilege key screen."""
        from tschan.tui.screens.privilege_key import PrivilegeKeyScreen

        self.app.push_screen(
            PrivilegeKeyScreen(self.privilege_key, self.config.server_name)
        )

    def _show_error(self, error_msg: str) -> None:
        """Display the error message on screen."""
        error_widget = self.query_one("#deploy-error", Static)
        error_widget.update(
            f"[bold #f87171]✗ Deployment failed:[/]\n"
            f"[#f87171]{error_msg}[/]\n\n"
            f"[#9ca3af]Press Escape to go back and try again.[/]"
        )
        # Re-enable escape
        self.BINDINGS = [("escape", "go_back", "Back")]

    def action_noop(self) -> None:
        """Disabled escape during deployment."""
        pass

    def action_go_back(self) -> None:
        """Go back after an error."""
        self.app.pop_screen()
