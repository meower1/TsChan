"""Single-page setup wizard screen for tschan."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape
from textual.message import Message
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox as _Checkbox,
    Header,
    Input,
    RadioButton as _RadioButton,
    RadioSet,
    Static,
)

class AdvanceCheckbox(_Checkbox):
    class Submitted(Message):
        pass
    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            self.post_message(self.Submitted())
        super().on_key(event)

class AdvanceRadioButton(_RadioButton):
    class Submitted(Message):
        pass
    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            self.post_message(self.Submitted())
        super().on_key(event)

from tschan.constants import (
    TEMPLATE_COZY_DEN,
    TEMPLATE_MEOWERS_HANGOUT,
    TEMPLATE_NEON_ARENA,
    TEMPLATE_SERVER_NAME_SUFFIX,
)
from tschan.models import SetupConfig
from tschan.templates.channels import get_template_preview
from tschan.templates.roles import ROLE_CATEGORIES


_TEMPLATE_KEYS = [TEMPLATE_MEOWERS_HANGOUT, TEMPLATE_NEON_ARENA, TEMPLATE_COZY_DEN]
_TEMPLATE_LABELS = [
    "Meower's Hangout",
    "Neon Arena",
    "Cozy Den",
]

_OPTIONAL_ROLE_KEYS = ["games", "cozy", "nerd_corner"]
_OPTIONAL_ROLE_LABELS = ["Games", "Cozy", "Nerd Corner"]


class SetupWizardScreen(Screen):
    """Setup wizard with all options on one page."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.config = SetupConfig()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        with Vertical(classes="wizard-content"):
            with Vertical(classes="wizard-column"):
                yield Static("Server name", classes="field-label")
                yield Input(
                    placeholder="e.g. meower",
                    id="server-name-input",
                )
                yield Static("", id="server-name-preview", classes="helper-text")

                yield Static("Melodify music bot", classes="field-label")
                with Horizontal(classes="inline-radio"):
                    with RadioSet(id="music-bot-radio-set"):
                        yield AdvanceRadioButton("Disabled", value=True, id="music-disable")
                        yield AdvanceRadioButton("Enabled", id="music-enable")
                yield Input(
                    placeholder="Melodify API key",
                    id="api-key-input",
                    password=True,
                )
                yield Static("", id="api-key-helper", classes="helper-text")

                yield Static("Cosmetic roles", classes="field-label")
                yield Static(
                    "[#6e7681]Staff always included[/]",
                    classes="helper-text",
                )
                with Horizontal(classes="inline-checkboxes"):
                    yield AdvanceCheckbox(
                        _OPTIONAL_ROLE_LABELS[0],
                        id="role-games",
                        value=False,
                    )
                    yield AdvanceCheckbox(
                        _OPTIONAL_ROLE_LABELS[1],
                        id="role-cozy",
                        value=False,
                    )
                    yield AdvanceCheckbox(
                        _OPTIONAL_ROLE_LABELS[2],
                        id="role-nerd-corner",
                        value=False,
                    )

                yield Static("Welcome message", classes="field-label")
                yield Input(
                    value="Welcome to the server!",
                    placeholder="Message shown when users connect",
                    id="welcome-message-input",
                )

            with Vertical(classes="wizard-column"):
                yield Static("Channel Template", classes="field-label")
                yield Static(
                    "[#6e7681]Choose the channel layout to create on the server.[/]",
                    classes="helper-text",
                )
                with RadioSet(id="template-radio-set"):
                    yield AdvanceRadioButton(_TEMPLATE_LABELS[0], value=True, id="tmpl-0")
                    yield AdvanceRadioButton(_TEMPLATE_LABELS[1], id="tmpl-1")
                    yield AdvanceRadioButton(_TEMPLATE_LABELS[2], id="tmpl-2")
                yield Static("", id="template-preview", classes="preview-panel")

        with Horizontal(classes="wizard-nav"):
            yield Button("Review", id="btn-review", variant="primary")


    def on_mount(self) -> None:
        """Initialize the wizard."""
        self._update_template_preview()
        self._update_api_key_visibility()
        self.query_one("#server-name-input", Input).focus()

    def _music_enabled_from_ui(self) -> bool:
        """Return True when the Melodify radio set is enabled."""
        radio_set = self.query_one("#music-bot-radio-set", RadioSet)
        return radio_set.pressed_index == 1

    def _save_all_data(self) -> None:
        """Persist all wizard options into config."""
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
            if self.query_one(widget_id, AdvanceCheckbox).value:
                groups.append(role_key)
        self.config.role_groups = groups

        radio_set = self.query_one("#template-radio-set", RadioSet)
        idx = radio_set.pressed_index
        if 0 <= idx < len(_TEMPLATE_KEYS):
            self.config.template_name = _TEMPLATE_KEYS[idx]

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
                f"[#6e7681]→ {escape(name + suffix)}[/]"
            )
        else:
            preview.update("")

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
        """Move from API key to cosmetic roles."""
        event.stop()
        self.query_one("#role-games", Checkbox).focus()

    @on(Input.Submitted, "#welcome-message-input")
    def _on_welcome_submitted(self, event: Input.Submitted) -> None:
        """Move from the last options input to the template picking."""
        event.stop()
        self.query_one("#template-radio-set", RadioSet).focus()

    @on(AdvanceCheckbox.Submitted)
    def _on_checkbox_submitted(self, event: AdvanceCheckbox.Submitted) -> None:
        """Move focus when pressing enter on any checkbox."""
        event.stop()
        self.query_one("#welcome-message-input", Input).focus()

    @on(AdvanceRadioButton.Submitted)
    def _on_radio_submitted(self, event: AdvanceRadioButton.Submitted) -> None:
        """Move focus when pressing enter on a radio button."""
        event.stop()
        if getattr(event.radio_button.parent, "id", None) == "music-bot-radio-set":
            if self._music_enabled_from_ui():
                self.query_one("#api-key-input", Input).focus()
            else:
                self.query_one("#role-games", AdvanceCheckbox).focus()
        elif getattr(event.radio_button.parent, "id", None) == "template-radio-set":
            self.query_one("#btn-review", Button).focus()

    @on(RadioSet.Changed, "#music-bot-radio-set")
    def _on_music_option_changed(self, event: RadioSet.Changed) -> None:
        """Show or hide the API key field when Melodify changes."""
        self._update_api_key_visibility()

    @on(RadioSet.Changed, "#template-radio-set")
    def _on_template_changed(self, event: RadioSet.Changed) -> None:
        """Update the channel preview when a template is selected."""
        self._update_template_preview()
        self._update_server_name_preview()

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
        self.app.exit()

    def _update_api_key_visibility(self) -> None:
        """Toggle the API key input visibility."""
        bot_on = self._music_enabled_from_ui()
        api_input = self.query_one("#api-key-input", Input)
        helper = self.query_one("#api-key-helper", Static)
        api_input.display = bot_on
        helper.display = bot_on
        if bot_on:
            helper.update("[#6e7681]API key required[/]")
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
            f"[#c9d1d9]{escape(preview_text)}[/]"
        )
