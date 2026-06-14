"""Two-page setup wizard screen for tschan."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Header,
    Input,
    RadioButton,
    RadioSet,
    Static,
)

from tschan.constants import (
    TEMPLATE_COZY_DEN,
    TEMPLATE_MEOWERS_HANGOUT,
    TEMPLATE_NEON_ARENA,
    TEMPLATE_SERVER_NAME_SUFFIX,
)
from tschan.models import SetupConfig
from tschan.templates.channels import get_template_preview
from tschan.templates.roles import ROLE_CATEGORIES


TOTAL_STEPS = 2

STEP_NAMES: list[str] = [
    "Server Options",
    "Channel Template",
]

_TEMPLATE_KEYS = [TEMPLATE_MEOWERS_HANGOUT, TEMPLATE_NEON_ARENA, TEMPLATE_COZY_DEN]
_TEMPLATE_LABELS = [
    "Meower's Hangout",
    "Neon Arena",
    "Cozy Den",
]

_OPTIONAL_ROLE_KEYS = ["games", "cozy", "nerd_corner"]
_OPTIONAL_ROLE_LABELS = ["Games", "Cozy", "Nerd Corner"]


class SetupWizardScreen(Screen):
    """Setup wizard with all options on one page except channel template."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.config = SetupConfig()
        self.current_step: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(id="step-indicator")

        with VerticalScroll(id="step-0", classes="wizard-content"):
            yield Static("Server Setup", classes="step-title")
            yield Static(
                "Configure the server options before choosing a template.",
                classes="step-subtitle",
            )

            with Vertical(classes="form-section"):
                yield Static("Server name", classes="field-label")
                yield Input(
                    placeholder="Server name, for example: meower",
                    id="server-name-input",
                )
                yield Static(
                    "Enter a server name to preview the final title.",
                    id="server-name-preview",
                    classes="helper-text",
                )

            with Vertical(classes="form-section"):
                yield Static("Melodify music bot", classes="field-label")
                with RadioSet(id="music-bot-radio-set"):
                    yield RadioButton("Disabled", value=True, id="music-disable")
                    yield RadioButton("Enabled", id="music-enable")
                yield Input(
                    placeholder="Melodify API key",
                    id="api-key-input",
                    password=True,
                )
                yield Static("", id="api-key-helper", classes="helper-text")

            with Vertical(classes="form-section"):
                yield Static("Cosmetic roles", classes="field-label")
                with Vertical(classes="role-category --locked"):
                    yield Static("Staff (always included)", classes="role-category-title")
                    yield Static(
                        "  ".join(ROLE_CATEGORIES["staff"]["roles"]),
                        classes="role-list",
                    )
                yield Checkbox(
                    _OPTIONAL_ROLE_LABELS[0],
                    id="role-games",
                    value=False,
                )
                yield Static("", id="roles-games-preview", classes="role-list")
                yield Checkbox(
                    _OPTIONAL_ROLE_LABELS[1],
                    id="role-cozy",
                    value=False,
                )
                yield Static("", id="roles-cozy-preview", classes="role-list")
                yield Checkbox(
                    _OPTIONAL_ROLE_LABELS[2],
                    id="role-nerd-corner",
                    value=False,
                )
                yield Static("", id="roles-nerd-corner-preview", classes="role-list")

            with Vertical(classes="form-section"):
                yield Static("Welcome message", classes="field-label")
                yield Input(
                    value="Welcome to the server!",
                    placeholder="Message shown when users connect",
                    id="welcome-message-input",
                )

        with VerticalScroll(id="step-1", classes="wizard-content"):
            yield Static("Channel Template", classes="step-title")
            yield Static(
                "Choose the channel layout to create on the server.",
                classes="step-subtitle",
            )
            with RadioSet(id="template-radio-set"):
                yield RadioButton(_TEMPLATE_LABELS[0], value=True, id="tmpl-0")
                yield RadioButton(_TEMPLATE_LABELS[1], id="tmpl-1")
                yield RadioButton(_TEMPLATE_LABELS[2], id="tmpl-2")
            yield Static("", id="template-preview", classes="preview-panel")

        with Horizontal(classes="wizard-nav"):
            yield Button("Back", id="btn-back", variant="default")
            yield Button("Next", id="btn-next", variant="primary")
            yield Button("Review", id="btn-review", variant="success")



    def on_mount(self) -> None:
        """Initialize the wizard."""
        self._sync_step_visibility()
        self._update_step_indicator()
        self._update_template_preview()
        self._update_role_previews()
        self._update_api_key_visibility()
        self.query_one("#server-name-input", Input).focus()

    def _sync_step_visibility(self) -> None:
        """Show only the current page."""
        for i in range(TOTAL_STEPS):
            container = self.query_one(f"#step-{i}")
            container.display = i == self.current_step

        self.query_one("#btn-back", Button).display = self.current_step > 0
        self.query_one("#btn-next", Button).display = self.current_step < TOTAL_STEPS - 1
        self.query_one("#btn-review", Button).display = self.current_step == TOTAL_STEPS - 1

    def _update_step_indicator(self) -> None:
        """Build the step indicator text."""
        parts: list[str] = []
        for i, name in enumerate(STEP_NAMES):
            if i < self.current_step:
                parts.append(f"[#34d399]✓ {name}[/]")
            elif i == self.current_step:
                parts.append(f"[bold #d8dee9]● {name}[/]")
            else:
                parts.append(f"[#8b949e]○ {name}[/]")
        self.query_one("#step-indicator", Static).update("  ─  ".join(parts))

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
        """Focus the primary widget on the current page."""
        widget_id = "#server-name-input" if self.current_step == 0 else "#template-radio-set"
        try:
            self.query_one(widget_id).focus()
        except Exception:
            pass

    def _music_enabled_from_ui(self) -> bool:
        """Return True when the Melodify radio set is enabled."""
        radio_set = self.query_one("#music-bot-radio-set", RadioSet)
        return radio_set.pressed_index == 1

    def _save_options_data(self) -> None:
        """Persist the consolidated options page into config."""
        self.config.server_name = self.query_one("#server-name-input", Input).value.strip()
        self.config.music_bot_enabled = self._music_enabled_from_ui()
        self.config.melodify_api_key = self.query_one("#api-key-input", Input).value.strip()
        self.config.welcome_message = self.query_one(
            "#welcome-message-input", Input
        ).value.strip()

        groups = ["staff"]
        for role_key, widget_id in zip(
            _OPTIONAL_ROLE_KEYS,
            ("#role-games", "#role-cozy", "#role-nerd-corner"),
            strict=True,
        ):
            if self.query_one(widget_id, Checkbox).value:
                groups.append(role_key)
        self.config.role_groups = groups

    def _save_template_data(self) -> None:
        """Persist the template page into config."""
        radio_set = self.query_one("#template-radio-set", RadioSet)
        idx = radio_set.pressed_index
        if 0 <= idx < len(_TEMPLATE_KEYS):
            self.config.template_name = _TEMPLATE_KEYS[idx]

    def _save_current_step_data(self) -> None:
        """Persist widget state for the current page."""
        if self.current_step == 0:
            self._save_options_data()
        elif self.current_step == 1:
            self._save_template_data()

    def _save_all_data(self) -> None:
        """Persist all wizard pages."""
        self._save_options_data()
        self._save_template_data()

    def _validate_current_step(self) -> str | None:
        """Validate the current page. Returns error text or None."""
        if self.current_step == 0:
            name = self.query_one("#server-name-input", Input).value.strip()
            if not name:
                return "Server name is required"
            if self._music_enabled_from_ui():
                key = self.query_one("#api-key-input", Input).value.strip()
                if not key:
                    return "Melodify API key is required when Melodify is enabled"
        return None

    @on(Input.Changed, "#server-name-input")
    def _on_name_changed(self, event: Input.Changed) -> None:
        """Live-update the final server title preview."""
        self._update_server_name_preview(event.value)

    def _update_server_name_preview(self, value: str | None = None) -> None:
        """Refresh the final server title preview."""
        if value is None:
            value = self.query_one("#server-name-input", Input).value
        name = value.strip()
        preview = self.query_one("#server-name-preview", Static)
        if name:
            suffix = TEMPLATE_SERVER_NAME_SUFFIX.get(
                self.config.template_name,
                "'s server",
            )
            preview.update(
                f"[#8b949e]Final server title:[/] "
                f"[bold #f0f6fc]{escape(name + suffix)}[/]"
            )
        else:
            preview.update("[#8b949e]Enter a server name to preview the final title.[/]")

    @on(Input.Submitted, "#server-name-input")
    def _on_name_submitted(self, event: Input.Submitted) -> None:
        """Move from server name to the next question."""
        event.stop()
        if not event.value.strip():
            self.notify("Server name is required", severity="error", title="Validation")
            return
        self.query_one("#music-bot-radio-set", RadioSet).focus()

    @on(Input.Submitted, "#api-key-input")
    def _on_api_key_submitted(self, event: Input.Submitted) -> None:
        """Move from API key to welcome message."""
        event.stop()
        self.query_one("#welcome-message-input", Input).focus()

    @on(Input.Submitted, "#welcome-message-input")
    def _on_welcome_submitted(self, event: Input.Submitted) -> None:
        """Move from the last options input to the template page."""
        event.stop()
        self.action_next_step()

    @on(RadioSet.Changed, "#music-bot-radio-set")
    def _on_music_option_changed(self, event: RadioSet.Changed) -> None:
        """Show or hide the API key field when Melodify changes."""
        self._update_api_key_visibility()

    @on(RadioSet.Changed, "#template-radio-set")
    def _on_template_changed(self, event: RadioSet.Changed) -> None:
        """Update the channel preview when a template is selected."""
        self._update_template_preview()
        self._update_server_name_preview()

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
                title="Validation Error",
                severity="error",
            )
            return
        from tschan.tui.screens.review import ReviewScreen

        self.app.push_screen(ReviewScreen(self.config, self, self.project_dir))

    def action_go_back(self) -> None:
        """Handle Escape key."""
        if self.current_step > 0:
            self.action_prev_step()
        else:
            self.app.exit()

    def action_prev_step(self) -> None:
        """Navigate to the previous page."""
        if self.current_step > 0:
            self._save_current_step_data()
            self._go_to_step(self.current_step - 1)

    def action_next_step(self) -> None:
        """Validate and navigate to the next page."""
        error = self._validate_current_step()
        if error:
            self.notify(error, severity="error", title="Validation")
            return
        if self.current_step < TOTAL_STEPS - 1:
            self._save_current_step_data()
            self._go_to_step(self.current_step + 1)

    def _update_api_key_visibility(self) -> None:
        """Toggle the API key input visibility."""
        bot_on = self._music_enabled_from_ui()
        api_input = self.query_one("#api-key-input", Input)
        helper = self.query_one("#api-key-helper", Static)
        api_input.display = bot_on
        helper.display = bot_on
        if bot_on:
            helper.update("[#8b949e]Required when Melodify is enabled.[/]")
        else:
            helper.update("")

    def _update_template_preview(self) -> None:
        """Refresh the channel tree preview for the selected template."""
        radio_set = self.query_one("#template-radio-set", RadioSet)
        idx = radio_set.pressed_index
        if idx < 0 or idx >= len(_TEMPLATE_KEYS):
            idx = 0
        key = _TEMPLATE_KEYS[idx]
        self.config.template_name = key
        preview_text = get_template_preview(key)
        self.query_one("#template-preview", Static).update(
            f"[#d8dee9]{escape(preview_text)}[/]"
        )

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
                preview.update("[#8b949e]  " + "  ·  ".join(escape(r) for r in roles) + "[/]")
            else:
                preview.update("")

    def jump_to_step(self, step: int) -> None:
        """Public method for the review screen to jump back to a page."""
        self._go_to_step(step)
