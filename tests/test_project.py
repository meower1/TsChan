from pathlib import Path

from tschan.constants import STATE_FILE
from tschan.project import DEFAULT_PROJECT_DIRNAME, default_project_dir, resolve_project_dir


def test_default_project_dir_uses_home(tmp_path: Path):
    home = tmp_path / "home"

    assert default_project_dir(home) == (home / DEFAULT_PROJECT_DIRNAME).resolve()


def test_resolve_project_dir_prefers_configured_cwd(tmp_path: Path):
    (tmp_path / STATE_FILE).write_text("{}", encoding="utf-8")

    assert resolve_project_dir(tmp_path, home=tmp_path / "home") == tmp_path.resolve()


def test_resolve_project_dir_falls_back_to_home_project(tmp_path: Path):
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    home = tmp_path / "home"

    assert resolve_project_dir(cwd, home=home) == (home / DEFAULT_PROJECT_DIRNAME).resolve()
