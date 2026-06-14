"""Privilege key display screen for tschan."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Center
from textual.screen import Screen
from textual.widgets import Button, Header, Static


class PrivilegeKeyScreen(Screen):
    """Displays the privilege key and connection instructions after deploy."""

    BINDINGS = [
        ("enter", "continue", "Continue"),
    ]

    def __init__(
        self,
        privilege_key: str,
        project_dir: Path,
        server_name: str = "",
    ) -> None:
        super().__init__()
        self.privilege_key = privilege_key
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.server_name = server_name

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Center():
            with Vertical(id="key-container"):
                yield Static(
                    "[bold #e2e8f0]Deployment Complete[/]",
                    classes="key-banner",
                )
                yield Static(
                    "\n[bold #e2e8f0]Your Privilege Key[/]\n",
                    classes="key-label",
                )
                yield Static(
                    f"[bold #fbbf24 on #161625]  {self.privilege_key}  [/]",
                    id="privilege-key-display",
                    classes="key-value",
                )
                yield Static(
                    "\n[bold #e2e8f0]Instructions[/]\n\n"
                    "[#c9d1d9]"
                    "  1. Open your [bold]TeamSpeak 3[/] client\n"
                    "  2. Connect to your server at [bold #fbbf24]localhost:9987[/]\n"
                    "  3. Go to [bold]Permissions → Use Privilege Key[/]\n"
                    "  4. Paste the key shown above\n"
                    "  5. You'll be granted the [bold #34d399]Dev[/] role "
                    "with full access\n"
                    "[/]\n"
                    "[#6e7681]Save this key. It is needed for the first login.[/]",
                    classes="key-instructions",
                )
                yield Static("", classes="spacer")
                yield Button(
                    "Continue to Management Panel",
                    id="btn-continue",
                    variant="primary",
                )


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-continue":
            self.action_continue()

    def action_continue(self) -> None:
        """Move to the management panel."""
        from tschan.engine.config_writer import load_config
        from tschan.tui.screens.management import ManagementScreen

        config = load_config(self.project_dir)
        if config is not None:
            self.app.switch_screen(ManagementScreen(config, self.project_dir))
        else:
            self.app.exit()
