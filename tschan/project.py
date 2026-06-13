"""Project directory resolution for tschan."""

from __future__ import annotations

from pathlib import Path

from tschan.constants import STATE_FILE


DEFAULT_PROJECT_DIRNAME = "tschan-server"


def default_project_dir(home: Path | None = None) -> Path:
    """Return the default managed project directory."""
    base = Path.home() if home is None else Path(home)
    return (base / DEFAULT_PROJECT_DIRNAME).expanduser().resolve()


def resolve_project_dir(
    cwd: Path | None = None,
    *,
    home: Path | None = None,
) -> Path:
    """Resolve the project directory for a CLI invocation.

    If the current working directory already contains a tschan state file, it
    remains the active project. Otherwise tschan uses the managed project under
    the user's home directory so the command can reopen management from
    anywhere after setup.
    """
    current_dir = Path.cwd() if cwd is None else Path(cwd)
    current_dir = current_dir.expanduser().resolve()
    if (current_dir / STATE_FILE).is_file():
        return current_dir
    return default_project_dir(home)
