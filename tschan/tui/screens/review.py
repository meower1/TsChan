"""Review screen — shows all config choices before deployment."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from tschan.constants import TEMPLATE_DISPLAY_NAMES
from tschan.models import SetupConfig
from tschan.templates.roles import ROLE_CATEGORIES

# Type alias for the wizard screen
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tschan.tui.screens.setup_wizard import SetupWizardScreen


class ReviewScreen(Screen):
    """Displays all configuration choices for final review before deploy."""

    BINDINGS = [
        ("escape", "go_back", "Back to Wizard"),
    ]

    def __init__(
        self,
        config: SetupConfig,
        wizard: SetupWizardScreen,
    ) -> None:
        super().__init__()
        self.config = config
        self.wizard = wizard

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "[bold #ff8fab]✦ ━━━  Review Your Setup  ━━━ ✦[/]",
            classes="step-title",
        )
        yield Static(
            "[#9ca3af]Double-check everything before deployment (◕‿◕✿)[/]",
            classes="step-subtitle",
        )

        with VerticalScroll(classes="wizard-content"):
            # ── Section 1: Server Name ───────────────────────────
            with VerticalScroll(classes="review-section"):
                yield Static(
                    "🏷️  Server Name",
                    classes="review-label",
                )
                yield Static(
                    "",
                    id="review-server-name",
                    classes="review-value",
                )
                yield Button(
                    "Edit",
                    id="edit-step-0",
                    variant="default",
                    classes="review-edit",
                )

            # ── Section 2: Music Bot ─────────────────────────────
            with VerticalScroll(classes="review-section"):
                yield Static(
                    "♪  Music Bot",
                    classes="review-label",
                )
                yield Static(
                    "",
                    id="review-music-bot",
                    classes="review-value",
                )
                yield Button(
                    "Edit",
                    id="edit-step-1",
                    variant="default",
                    classes="review-edit",
                )

            # ── Section 3: Channel Template ──────────────────────
            with VerticalScroll(classes="review-section"):
                yield Static(
                    "🏠  Channel Template",
                    classes="review-label",
                )
                yield Static(
                    "",
                    id="review-template",
                    classes="review-value",
                )
                yield Button(
                    "Edit",
                    id="edit-step-2",
                    variant="default",
                    classes="review-edit",
                )

            # ── Section 4: Cosmetic Roles ────────────────────────
            with VerticalScroll(classes="review-section"):
                yield Static(
                    "👑  Cosmetic Roles",
                    classes="review-label",
                )
                yield Static(
                    "",
                    id="review-roles",
                    classes="review-value",
                )
                yield Button(
                    "Edit",
                    id="edit-step-3",
                    variant="default",
                    classes="review-edit",
                )

            # ── Section 5: Welcome Message ───────────────────────
            with VerticalScroll(classes="review-section"):
                yield Static(
                    "💌  Welcome Message",
                    classes="review-label",
                )
                yield Static(
                    "",
                    id="review-welcome",
                    classes="review-value",
                )
                yield Button(
                    "Edit",
                    id="edit-step-4",
                    variant="default",
                    classes="review-edit",
                )

            # ── Deploy button ────────────────────────────────────
            yield Static("", classes="sakura-divider")
            with Horizontal(classes="wizard-nav"):
                yield Button(
                    "← Back to Wizard",
                    id="btn-review-back",
                    variant="default",
                )
                yield Button(
                    "🌸 Deploy",
                    id="btn-deploy",
                    variant="success",
                )

        yield Footer()

    def on_mount(self) -> None:
        """Populate the review fields from config."""
        self._populate()

    def _populate(self) -> None:
        """Fill in all review sections from the config."""
        c = self.config

        # Server name
        template_display = TEMPLATE_DISPLAY_NAMES.get(
            c.template_name, "{name}'s server"
        )
        full_name = template_display.replace("{name}", c.server_name)
        self.query_one("#review-server-name", Static).update(
            f"[bold #faf5ff]{full_name}[/]"
        )

        # Music bot
        if c.music_bot_enabled:
            masked_key = c.melodify_api_key[:4] + "••••" + c.melodify_api_key[-4:]
            self.query_one("#review-music-bot", Static).update(
                f"[#34d399]Enabled[/]  ·  Key: [#9ca3af]{masked_key}[/]"
            )
        else:
            self.query_one("#review-music-bot", Static).update(
                "[#9ca3af]Disabled[/]"
            )

        # Template
        tmpl_name = TEMPLATE_DISPLAY_NAMES.get(c.template_name, c.template_name)
        self.query_one("#review-template", Static).update(
            f"[#c4b5fd]{tmpl_name}[/]"
        )

        # Roles
        role_parts: list[str] = []
        for group in c.role_groups:
            cat = ROLE_CATEGORIES.get(group)
            if cat:
                role_parts.append(f"[#ff8fab]{cat['display']}[/]")
        self.query_one("#review-roles", Static).update(
            "\n".join(role_parts) if role_parts else "[#9ca3af]Staff only[/]"
        )

        # Welcome message
        msg = c.welcome_message or "(no message)"
        self.query_one("#review-welcome", Static).update(
            f"[#e8e0f0]{msg}[/]"
        )

    # ── Event Handlers ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#edit-step-0")
    def _edit_step_0(self) -> None:
        self._jump_to_wizard(0)

    @on(Button.Pressed, "#edit-step-1")
    def _edit_step_1(self) -> None:
        self._jump_to_wizard(1)

    @on(Button.Pressed, "#edit-step-2")
    def _edit_step_2(self) -> None:
        self._jump_to_wizard(2)

    @on(Button.Pressed, "#edit-step-3")
    def _edit_step_3(self) -> None:
        self._jump_to_wizard(3)

    @on(Button.Pressed, "#edit-step-4")
    def _edit_step_4(self) -> None:
        self._jump_to_wizard(4)

    @on(Button.Pressed, "#btn-review-back")
    def _on_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-deploy")
    def _on_deploy(self) -> None:
        """Proceed to the deployment screen."""
        from tschan.tui.screens.deploying import DeployingScreen

        self.app.push_screen(DeployingScreen(self.config))

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _jump_to_wizard(self, step: int) -> None:
        """Pop back to wizard and jump to the given step."""
        self.wizard.jump_to_step(step)
        self.app.pop_screen()
