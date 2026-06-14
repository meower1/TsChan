"""🌸 tschan — Main Textual Application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from tschan.constants import STATE_FILE
from tschan.project import resolve_project_dir


class TschanApp(App[None]):
    """🌸 tschan — TeamSpeak 3 Template Generator."""

    CSS_PATH = "styles/theme.tcss"
    TITLE = "tschan"
    SUB_TITLE = ""
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        force_setup: bool = False,
        project_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.force_setup = force_setup
        self.project_dir = (
            resolve_project_dir() if project_dir is None else Path(project_dir)
        ).expanduser().resolve()

    def on_mount(self) -> None:
        """Decide which screen to show based on existing config."""
        state_path = self.project_dir / STATE_FILE
        if state_path.exists() and not self.force_setup:
            from tschan.engine.config_writer import load_config
            from tschan.tui.screens.management import ManagementScreen

            config = load_config(self.project_dir)
            if config is not None:
                self.push_screen(ManagementScreen(config, self.project_dir))
                return

        from tschan.tui.screens.setup_wizard import SetupWizardScreen

        self.push_screen(SetupWizardScreen(self.project_dir))
