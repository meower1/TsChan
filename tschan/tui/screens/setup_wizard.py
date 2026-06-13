"""Multi-step setup wizard screen for tschan."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
    Switch,
    TextArea,
)

from tschan.constants import (
    TEMPLATE_COZY_DEN,
    TEMPLATE_DISPLAY_NAMES,
    TEMPLATE_MEOWERS_HANGOUT,
    TEMPLATE_NEON_ARENA,
)
from tschan.models import SetupConfig
from tschan.templates.channels import get_template_preview
from tschan.templates.roles import ROLE_CATEGORIES

# ── Constants ────────────────────────────────────────────────────────────────

TOTAL_STEPS = 5

STEP_NAMES: list[str] = [
    "Server Name",
    "Music Bot",
    "Channel Template",
    "Cosmetic Roles",
    "Welcome Message",
]

_TEMPLATE_KEYS = [TEMPLATE_MEOWERS_HANGOUT, TEMPLATE_NEON_ARENA, TEMPLATE_COZY_DEN]
_TEMPLATE_LABELS = [
    "🐱 meower's hangout",
    "⚡ neon arena",
    "☕ the cozy den",
]

_OPTIONAL_ROLE_KEYS = ["games", "cozy", "nerd_corner"]
_OPTIONAL_ROLE_LABELS = ["Games 🎮", "Cozy ☁️", "Nerd Corner 🖥️"]


# ── Setup Wizard Screen ─────────────────────────────────────────────────────


class SetupWizardScreen(Screen):
    """Multi-step setup wizard — 5 steps + review."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("left", "prev_step", "Previous"),
        ("right", "next_step", "Next"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = SetupConfig()
        self.current_step: int = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="step-indicator")

        # ── Step 1: Server Name ──────────────────────────────────
        with VerticalScroll(id="step-0", classes="wizard-content"):
            yield Static(
                "✦ What's your name? ✦",
                classes="step-title",
            )
            yield Static(
                "(this becomes your server's identity)",
                classes="step-subtitle",
            )
            yield Input(
                placeholder="Enter your name (e.g., meower)",
                id="server-name-input",
            )
            yield Static(
                "Your server will be named '...'s hangout'",
                id="server-name-preview",
                classes="helper-text",
            )

        # ── Step 2: Music Bot ────────────────────────────────────
        with VerticalScroll(id="step-1", classes="wizard-content"):
            yield Static(
                "♪ Music Bot Setup ♪",
                classes="step-title",
            )
            yield Static(
                "Enable Melodify music bot?",
                classes="step-subtitle",
            )
            with Horizontal(id="music-switch-row"):
                yield Label("Enable Melodify  ")
                yield Switch(id="music-bot-switch", value=False)
            yield Static(
                "(requires Melodify backend API key)",
                classes="muted-text",
            )
            yield Input(
                placeholder="Paste your Melodify API key here",
                id="api-key-input",
                password=True,
            )
            yield Static(
                "",
                id="api-key-helper",
                classes="helper-text",
            )

        # ── Step 3: Channel Template ─────────────────────────────
        with VerticalScroll(id="step-2", classes="wizard-content"):
            yield Static(
                "🏠 Choose a Channel Template",
                classes="step-title",
            )
            yield Static(
                "(see TEMPLATES.md for full showcase)",
                classes="step-subtitle",
            )
            with RadioSet(id="template-radio-set"):
                yield RadioButton(_TEMPLATE_LABELS[0], value=True, id="tmpl-0")
                yield RadioButton(_TEMPLATE_LABELS[1], id="tmpl-1")
                yield RadioButton(_TEMPLATE_LABELS[2], id="tmpl-2")
            yield Static(
                "",
                id="template-preview",
                classes="preview-panel",
            )

        # ── Step 4: Cosmetic Roles ───────────────────────────────
        with VerticalScroll(id="step-3", classes="wizard-content"):
            yield Static(
                "👑 Cosmetic Roles",
                classes="step-title",
            )
            yield Static(
                "Choose additional role groups for your server",
                classes="step-subtitle",
            )
            # Staff — always included, shown locked
            with Vertical(classes="role-category --locked"):
                yield Static(
                    "🔒 Staff  (always included)",
                    classes="role-category-title",
                )
                yield Static(
                    "  ".join(ROLE_CATEGORIES["staff"]["roles"]),
                    classes="role-list",
                )
            yield Checkbox(
                _OPTIONAL_ROLE_LABELS[0],
                id="role-games",
                value=False,
            )
            yield Static(
                "",
                id="roles-games-preview",
                classes="role-list",
            )
            yield Checkbox(
                _OPTIONAL_ROLE_LABELS[1],
                id="role-cozy",
                value=False,
            )
            yield Static(
                "",
                id="roles-cozy-preview",
                classes="role-list",
            )
            yield Checkbox(
                _OPTIONAL_ROLE_LABELS[2],
                id="role-nerd-corner",
                value=False,
            )
            yield Static(
                "",
                id="roles-nerd-corner-preview",
                classes="role-list",
            )

        # ── Step 5: Welcome Message ──────────────────────────────
        with VerticalScroll(id="step-4", classes="wizard-content"):
            yield Static(
                "💌 Welcome Message",
                classes="step-title",
            )
            yield Static(
                "This message appears when players connect",
                classes="step-subtitle",
            )
            yield TextArea(
                "Welcome to the server! Enjoy your stay ✨",
                id="welcome-message-area",
            )
            yield Static(
                "(◕‿◕✿) tip: you can use TS3 BB-code for formatting",
                classes="helper-text",
            )

        # ── Navigation bar ───────────────────────────────────────
        with Horizontal(classes="wizard-nav"):
            yield Button("← Back", id="btn-back", variant="default")
            yield Button("Next →", id="btn-next", variant="primary")
            yield Button("🌸 Review", id="btn-review", variant="success")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the wizard to step 0."""
        self._sync_step_visibility()
        self._update_step_indicator()
        self._update_template_preview()
        self._update_role_previews()
        self._update_api_key_visibility()
        self.query_one("#server-name-input", Input).focus()

    # ── Step Navigation ──────────────────────────────────────────────────────

    def _sync_step_visibility(self) -> None:
        """Show only the current step's content container."""
        for i in range(TOTAL_STEPS):
            container = self.query_one(f"#step-{i}")
            container.display = i == self.current_step

        # Show/hide nav buttons appropriately
        btn_back = self.query_one("#btn-back", Button)
        btn_next = self.query_one("#btn-next", Button)
        btn_review = self.query_one("#btn-review", Button)

        btn_back.display = self.current_step > 0
        btn_next.display = self.current_step < TOTAL_STEPS - 1
        btn_review.display = self.current_step == TOTAL_STEPS - 1

    def _update_step_indicator(self) -> None:
        """Build the step indicator text with checkmarks."""
        parts: list[str] = []
        for i, name in enumerate(STEP_NAMES):
            if i < self.current_step:
                parts.append(f"[#34d399]✓ {name}[/]")
            elif i == self.current_step:
                parts.append(f"[bold #ff8fab]● {name}[/]")
            else:
                parts.append(f"[#9ca3af]○ {name}[/]")
        indicator = self.query_one("#step-indicator", Static)
        indicator.update("  ─  ".join(parts))

    def _go_to_step(self, step: int) -> None:
        """Navigate to the specified step, clamped to valid range."""
        step = max(0, min(step, TOTAL_STEPS - 1))
        if step == self.current_step:
            return
        self._save_current_step_data()
        self.current_step = step
        self._sync_step_visibility()
        self._update_step_indicator()
        self._focus_current_step()

    def _focus_current_step(self) -> None:
        """Focus the primary widget in the current step."""
        focus_map: dict[int, str] = {
            0: "#server-name-input",
            1: "#music-bot-switch",
            2: "#template-radio-set",
            3: "#role-games",
            4: "#welcome-message-area",
        }
        widget_id = focus_map.get(self.current_step)
        if widget_id:
            try:
                self.query_one(widget_id).focus()
            except Exception:
                pass

    # ── Data Sync ────────────────────────────────────────────────────────────

    def _save_current_step_data(self) -> None:
        """Persist widget state → config object for the current step."""
        if self.current_step == 0:
            self.config.server_name = self.query_one(
                "#server-name-input", Input
            ).value.strip()
        elif self.current_step == 1:
            self.config.music_bot_enabled = self.query_one(
                "#music-bot-switch", Switch
            ).value
            self.config.melodify_api_key = self.query_one(
                "#api-key-input", Input
            ).value.strip()
        elif self.current_step == 2:
            radio_set = self.query_one("#template-radio-set", RadioSet)
            idx = radio_set.pressed_index
            if idx >= 0 and idx < len(_TEMPLATE_KEYS):
                self.config.template_name = _TEMPLATE_KEYS[idx]
        elif self.current_step == 3:
            groups = ["staff"]  # always included
            if self.query_one("#role-games", Checkbox).value:
                groups.append("games")
            if self.query_one("#role-cozy", Checkbox).value:
                groups.append("cozy")
            if self.query_one("#role-nerd-corner", Checkbox).value:
                groups.append("nerd_corner")
            self.config.role_groups = groups
        elif self.current_step == 4:
            self.config.welcome_message = self.query_one(
                "#welcome-message-area", TextArea
            ).text.strip()

    def _save_all_data(self) -> None:
        """Save data from all steps."""
        saved = self.current_step
        for step in range(TOTAL_STEPS):
            self.current_step = step
            self._save_current_step_data()
        self.current_step = saved

    def _validate_current_step(self) -> str | None:
        """Validate the current step. Returns error message or None."""
        if self.current_step == 0:
            name = self.query_one("#server-name-input", Input).value.strip()
            if not name:
                return "Server name is required (◕︵◕)"
        elif self.current_step == 1:
            bot_on = self.query_one("#music-bot-switch", Switch).value
            key = self.query_one("#api-key-input", Input).value.strip()
            if bot_on and not key:
                return "API key is required when Melodify is enabled (◕︵◕)"
        return None

    # ── Event Handlers ───────────────────────────────────────────────────────

    @on(Input.Changed, "#server-name-input")
    def _on_name_changed(self, event: Input.Changed) -> None:
        """Live-update the server name preview."""
        name = event.value.strip()
        preview = self.query_one("#server-name-preview", Static)
        if name:
            template_key = self.config.template_name
            display = TEMPLATE_DISPLAY_NAMES.get(template_key, "{name}'s server")
            display_name = display.replace("{name}", name)
            preview.update(
                f"[#a78bfa]Your server will be named:[/] "
                f"[bold #ff8fab]{display_name}[/]  (◕‿◕✿)"
            )
        else:
            preview.update("[#9ca3af]Enter your name above...[/]")

    @on(Switch.Changed, "#music-bot-switch")
    def _on_music_switch(self, event: Switch.Changed) -> None:
        """Show/hide the API key input when the switch toggles."""
        self._update_api_key_visibility()
        helper = self.query_one("#api-key-helper", Static)
        if event.value:
            helper.update("[#a78bfa]♪ Melodify will serve music to your server ♪[/]")
        else:
            helper.update("")

    @on(RadioSet.Changed, "#template-radio-set")
    def _on_template_changed(self, event: RadioSet.Changed) -> None:
        """Update the channel preview when a template is selected."""
        self._update_template_preview()

    @on(Checkbox.Changed, "#role-games")
    @on(Checkbox.Changed, "#role-cozy")
    @on(Checkbox.Changed, "#role-nerd-corner")
    def _on_role_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Update role previews when checkboxes toggle."""
        self._update_role_previews()

    @on(Button.Pressed, "#btn-back")
    def _on_back(self) -> None:
        self.action_prev_step()

    @on(Button.Pressed, "#btn-next")
    def _on_next(self) -> None:
        self.action_next_step()

    @on(Button.Pressed, "#btn-review")
    def _on_review(self) -> None:
        """Validate and go to review screen."""
        self._save_all_data()
        errors = self.config.validate()
        if errors:
            self.notify(
                "\n".join(errors),
                title="Validation Error (◕︵◕)",
                severity="error",
            )
            return
        from tschan.tui.screens.review import ReviewScreen

        self.app.push_screen(ReviewScreen(self.config, self))

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        """Handle Escape key — go to previous step or exit."""
        if self.current_step > 0:
            self.action_prev_step()
        else:
            self.app.exit()

    def action_prev_step(self) -> None:
        """Navigate to the previous step."""
        if self.current_step > 0:
            self._save_current_step_data()
            self._go_to_step(self.current_step - 1)

    def action_next_step(self) -> None:
        """Validate and navigate to the next step."""
        error = self._validate_current_step()
        if error:
            self.notify(error, severity="error", title="Hold on!")
            return
        self._save_current_step_data()
        self._go_to_step(self.current_step + 1)

    # ── UI Helpers ───────────────────────────────────────────────────────────

    def _update_api_key_visibility(self) -> None:
        """Toggle the API key input visibility."""
        bot_on = self.query_one("#music-bot-switch", Switch).value
        api_input = self.query_one("#api-key-input", Input)
        api_input.display = bot_on

    def _update_template_preview(self) -> None:
        """Refresh the channel tree preview for the selected template."""
        radio_set = self.query_one("#template-radio-set", RadioSet)
        idx = radio_set.pressed_index
        if idx < 0 or idx >= len(_TEMPLATE_KEYS):
            idx = 0
        key = _TEMPLATE_KEYS[idx]
        preview_text = get_template_preview(key)
        preview = self.query_one("#template-preview", Static)
        preview.update(f"[#c4b5fd]{preview_text}[/]")

    def _update_role_previews(self) -> None:
        """Show roles under each selected category."""
        mapping = {
            "#role-games": ("games", "#roles-games-preview"),
            "#role-cozy": ("cozy", "#roles-cozy-preview"),
            "#role-nerd-corner": ("nerd_corner", "#roles-nerd-corner-preview"),
        }
        for cb_id, (cat_key, preview_id) in mapping.items():
            checked = self.query_one(cb_id, Checkbox).value
            preview = self.query_one(preview_id, Static)
            if checked:
                roles = ROLE_CATEGORIES[cat_key]["roles"]
                preview.update("[#c4b5fd]  " + "  ·  ".join(roles) + "[/]")
            else:
                preview.update("")

    def jump_to_step(self, step: int) -> None:
        """Public method for the review screen to jump back to a step."""
        self._go_to_step(step)
