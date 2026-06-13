"""Review screen showing all config choices before deployment."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from tschan.constants import TEMPLATE_SERVER_NAME_SUFFIX
from tschan.models import SetupConfig

if TYPE_CHECKING:
    from tschan.tui.screens.setup_wizard import SetupWizardScreen


_TEMPLATE_NAMES = {
    "meowers_hangout": "Meower's Hangout",
    "neon_arena": "Neon Arena",
    "cozy_den": "Cozy Den",
}

_ROLE_NAMES = {
    "staff": "Staff",
    "games": "Games",
    "cozy": "Cozy",
    "nerd_corner": "Nerd Corner",
}


class ReviewScreen(Screen):
    """Displays all configuration choices for final review before deploy."""

    BINDINGS = [
        ("escape", "go_back", "Back to setup"),
    ]

    def __init__(
        self,
        config: SetupConfig,
        wizard: SetupWizardScreen,
        project_dir: Path,
    ) -> None:
        super().__init__()
        self.config = config
        self.wizard = wizard
        self.project_dir = Path(project_dir).expanduser().resolve()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Review Your Setup", classes="step-title")
        yield Static(
            "Confirm these values before deployment.",
            classes="step-subtitle",
        )

        with VerticalScroll(classes="wizard-content review-content"):
            with Horizontal(classes="review-row"):
                yield Static("Project folder", classes="review-label")
                yield Static(
                    f"[#f0f6fc]{escape(str(self.project_dir))}[/]",
                    id="review-project-dir",
                    classes="review-value",
                )
                yield Static("", classes="review-spacer")

            with Horizontal(classes="review-row"):
                yield Static("Server name", classes="review-label")
                yield Static(
                    self._server_name_value(),
                    id="review-server-name",
                    classes="review-value",
                )
                yield Button("Edit", id="edit-step-0", variant="default")

            with Horizontal(classes="review-row"):
                yield Static("Melodify", classes="review-label")
                yield Static(
                    self._music_value(),
                    id="review-music-bot",
                    classes="review-value",
                )
                yield Button("Edit", id="edit-step-0-music", variant="default")

            with Horizontal(classes="review-row"):
                yield Static("Channel template", classes="review-label")
                yield Static(
                    self._template_value(),
                    id="review-template",
                    classes="review-value",
                )
                yield Button("Edit", id="edit-step-1", variant="default")

            with Horizontal(classes="review-row"):
                yield Static("Cosmetic roles", classes="review-label")
                yield Static(
                    self._roles_value(),
                    id="review-roles",
                    classes="review-value",
                )
                yield Button("Edit", id="edit-step-0-roles", variant="default")

            with Horizontal(classes="review-row"):
                yield Static("Welcome message", classes="review-label")
                yield Static(
                    self._welcome_value(),
                    id="review-welcome",
                    classes="review-value",
                )
                yield Button("Edit", id="edit-step-0-welcome", variant="default")

        with Horizontal(classes="wizard-nav"):
            yield Button("Back to Setup", id="btn-review-back", variant="default")
            yield Button("Deploy", id="btn-deploy", variant="success")

        yield Footer()

    def _server_name_value(self) -> str:
        name = self.config.server_name.strip()
        if not name:
            return "[#8b949e]Not set[/]"
        suffix = TEMPLATE_SERVER_NAME_SUFFIX.get(self.config.template_name, "'s server")
        return f"[#f0f6fc]{escape(name + suffix)}[/]"

    def _music_value(self) -> str:
        if not self.config.music_bot_enabled:
            return "[#8b949e]Disabled[/]"
        key = self.config.melodify_api_key.strip()
        if not key:
            return "[#f85149]Enabled, API key missing[/]"
        if len(key) <= 8:
            masked_key = "•" * len(key)
        else:
            masked_key = f"{key[:4]}••••{key[-4:]}"
        return f"[#3fb950]Enabled[/] [#8b949e]· Key {escape(masked_key)}[/]"

    def _template_value(self) -> str:
        name = _TEMPLATE_NAMES.get(self.config.template_name, self.config.template_name)
        return f"[#f0f6fc]{escape(name)}[/]"

    def _roles_value(self) -> str:
        role_names = [
            _ROLE_NAMES.get(group, group)
            for group in self.config.role_groups
            if group in _ROLE_NAMES
        ]
        if not role_names:
            role_names = ["Staff"]
        return f"[#f0f6fc]{escape(', '.join(role_names))}[/]"

    def _welcome_value(self) -> str:
        message = self.config.welcome_message.strip()
        if not message:
            return "[#8b949e]No welcome message[/]"
        return f"[#f0f6fc]{escape(message)}[/]"

    @on(Button.Pressed, "#edit-step-0")
    @on(Button.Pressed, "#edit-step-0-music")
    @on(Button.Pressed, "#edit-step-0-roles")
    @on(Button.Pressed, "#edit-step-0-welcome")
    def _edit_options(self) -> None:
        self._jump_to_wizard(0)

    @on(Button.Pressed, "#edit-step-1")
    def _edit_template(self) -> None:
        self._jump_to_wizard(1)

    @on(Button.Pressed, "#btn-review-back")
    def _on_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-deploy")
    def _on_deploy(self) -> None:
        """Proceed to the deployment screen."""
        from tschan.tui.screens.deploying import DeployingScreen

        self.app.push_screen(DeployingScreen(self.config, self.project_dir))

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _jump_to_wizard(self, step: int) -> None:
        """Pop back to wizard and jump to the given step."""
        self.wizard.jump_to_step(step)
        self.app.pop_screen()
