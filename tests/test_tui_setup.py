import asyncio
from pathlib import Path

from textual.app import App
from textual.widgets import Input, Static

from tschan.models import SetupConfig
from tschan.tui.app import TschanApp
from tschan.tui.screens.deploying import DeployingScreen
from tschan.tui.screens.review import ReviewScreen
from tschan.tui.screens.setup_wizard import SetupWizardScreen


def run_async(coro):
    return asyncio.run(coro)


def test_setup_uses_two_pages_and_project_dir(tmp_path: Path):
    async def scenario():
        app = TschanApp(project_dir=tmp_path)
        async with app.run_test(size=(120, 40)):
            screen = app.screen
            assert isinstance(screen, SetupWizardScreen)
            assert screen.project_dir == tmp_path.resolve()
            assert screen.query_one("#step-0").display is True
            assert screen.query_one("#step-1").display is False

    run_async(scenario())


def test_enter_from_server_name_moves_to_next_question(tmp_path: Path):
    async def scenario():
        app = TschanApp(project_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("m", "e", "o", "w", "e", "r")
            await pilot.press("enter")

            focused = app.focused
            assert focused is not None
            assert focused.id == "music-bot-radio-set"

    run_async(scenario())


def test_melodify_radio_controls_api_key_visibility(tmp_path: Path):
    async def scenario():
        app = TschanApp(project_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.screen
            api_key_input = screen.query_one("#api-key-input", Input)
            assert api_key_input.display is False

            await pilot.click("#music-enable")
            assert api_key_input.display is True

            await pilot.click("#music-disable")
            assert api_key_input.display is False

    run_async(scenario())


def test_welcome_enter_moves_to_template_page(tmp_path: Path):
    async def scenario():
        app = TschanApp(project_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("m", "e", "o", "w", "e", "r")
            screen = app.screen
            screen.query_one("#welcome-message-input", Input).focus()
            await pilot.press("enter")

            assert screen.current_step == 1
            assert screen.query_one("#step-0").display is False
            assert screen.query_one("#step-1").display is True

    run_async(scenario())


class ReviewHarness(App[None]):
    def __init__(self, config: SetupConfig, project_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.project_dir = project_dir

    def on_mount(self) -> None:
        wizard = SetupWizardScreen(self.project_dir)
        self.push_screen(ReviewScreen(self.config, wizard, self.project_dir))


def test_review_screen_renders_non_empty_values(tmp_path: Path):
    async def scenario():
        config = SetupConfig(
            server_name="meower",
            music_bot_enabled=True,
            melodify_api_key="abcd1234efgh",
            template_name="neon_arena",
            role_groups=["staff", "games"],
            welcome_message="Welcome in.",
        )
        app = ReviewHarness(config, tmp_path)
        async with app.run_test(size=(120, 40)):
            screen = app.screen
            assert "meower" in str(screen.query_one("#review-server-name", Static).content)
            assert "Enabled" in str(screen.query_one("#review-music-bot", Static).content)
            assert "Neon Arena" in str(screen.query_one("#review-template", Static).content)
            assert "Staff, Games" in str(screen.query_one("#review-roles", Static).content)
            assert "Welcome in." in str(screen.query_one("#review-welcome", Static).content)

    run_async(scenario())


class DeployNoRunScreen(DeployingScreen):
    def on_mount(self) -> None:
        pass


class DeployHarness(App[None]):
    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = project_dir

    def on_mount(self) -> None:
        self.push_screen(DeployNoRunScreen(SetupConfig(server_name="meower"), self.project_dir))


def test_deploy_progress_marks_active_done_and_error(tmp_path: Path):
    async def scenario():
        app = DeployHarness(tmp_path)
        async with app.run_test(size=(120, 40)):
            screen = app.screen
            assert isinstance(screen, DeployNoRunScreen)
            screen._prepare_log_file()
            screen._append_log_line("manual log entry")
            assert (tmp_path / "tschan-deploy.log").exists()
            assert "manual log entry" in (tmp_path / "tschan-deploy.log").read_text()

            screen._set_step_active(0)
            assert screen._active_step_index == 0
            assert "Writing configuration files" in str(
                screen.query_one("#deploy-status", Static).content
            )

            screen._set_step_done(0)
            assert "Completed 1 of" in str(
                screen.query_one("#deploy-status", Static).content
            )

            screen._show_error("boom")
            assert screen._failed is True
            assert "boom" in str(screen.query_one("#deploy-error", Static).content)
            log_text = (tmp_path / "tschan-deploy.log").read_text()
            assert "Step 1/" in log_text
            assert "Deployment failed" in log_text

    run_async(scenario())
