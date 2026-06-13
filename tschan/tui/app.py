"""🌸 tschan — Main Textual Application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from tschan.constants import STATE_FILE


class TschanApp(App[None]):
    """🌸 tschan — TeamSpeak 3 Template Generator."""

    CSS_PATH = "styles/theme.tcss"
    TITLE = "tschan ✦ TS3 Template Generator"
    SUB_TITLE = "🌸 making teamspeak pretty since 2024"

    def __init__(self, force_setup: bool = False) -> None:
        super().__init__()
        self.force_setup = force_setup

    def on_mount(self) -> None:
        """Decide which screen to show based on existing config."""
        state_path = Path.cwd() / STATE_FILE
        if state_path.exists() and not self.force_setup:
            from tschan.engine.config_writer import load_config
            from tschan.tui.screens.management import ManagementScreen

            config = load_config(Path.cwd())
            if config is not None:
                self.push_screen(ManagementScreen(config))
                return

        from tschan.tui.screens.setup_wizard import SetupWizardScreen

        self.push_screen(SetupWizardScreen())
