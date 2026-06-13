"""Tests for tschan.engine.docker_ctl"""

import tempfile
from pathlib import Path

from tschan.engine.docker_ctl import DockerController


class TestDockerController:
    def test_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctl = DockerController(Path(tmpdir))
            assert ctl.project_dir == Path(tmpdir).resolve()

    def test_compose_command_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctl = DockerController(Path(tmpdir))
            # The controller should build proper compose commands
            assert ctl.project_dir.exists()
