"""Tests for tschan.engine.config_writer"""

import json
import tempfile
from pathlib import Path

from tschan.models import SetupConfig
from tschan.engine.config_writer import (
    generate_env,
    generate_docker_compose,
    write_all,
    load_config,
)
from tschan.constants import STATE_FILE, DATA_DIR


class TestGenerateEnv:
    def test_contains_query_password(self):
        config = SetupConfig(server_name="test")
        env = generate_env(config)
        assert f"TS3_QUERY_PASSWORD={config.query_password}" in env

    def test_contains_debug_token(self):
        config = SetupConfig(server_name="test")
        env = generate_env(config)
        assert config.debug_token in env

    def test_music_bot_enabled(self):
        config = SetupConfig(
            server_name="test",
            music_bot_enabled=True,
            melodify_api_key="mykey123",
        )
        env = generate_env(config)
        assert "MELODIFY_API_KEY=mykey123" in env

    def test_iran_mirrors(self):
        config = SetupConfig(server_name="test", iran_mirrors=True)
        env = generate_env(config)
        assert "devneeds" in env

    def test_no_iran_mirrors(self):
        config = SetupConfig(server_name="test", iran_mirrors=False)
        env = generate_env(config)
        assert "devneeds" not in env or "# " in env.split("devneeds")[0].split("\n")[-1]


class TestGenerateDockerCompose:
    def test_contains_teamspeak_service(self):
        config = SetupConfig(server_name="test")
        compose = generate_docker_compose(config)
        assert "teamspeak" in compose

    def test_music_bot_services_included(self):
        config = SetupConfig(
            server_name="test",
            music_bot_enabled=True,
            melodify_api_key="key",
        )
        compose = generate_docker_compose(config)
        assert "ts3audiobot" in compose
        assert "python-orchestrator" in compose

    def test_music_bot_services_excluded(self):
        config = SetupConfig(server_name="test", music_bot_enabled=False)
        compose = generate_docker_compose(config)
        assert "ts3audiobot" not in compose
        assert "python-orchestrator" not in compose

    def test_iran_image(self):
        config = SetupConfig(server_name="test", iran_mirrors=True)
        compose = generate_docker_compose(config)
        assert "devneeds" in compose

    def test_default_image(self):
        config = SetupConfig(server_name="test", iran_mirrors=False)
        compose = generate_docker_compose(config)
        assert "mbentley/teamspeak" in compose


class TestWriteAllAndLoadConfig:
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SetupConfig(
                server_name="testuser",
                music_bot_enabled=True,
                melodify_api_key="testkey",
                template_name="neon_arena",
                role_groups=["staff", "games"],
                welcome_message="Hello!",
                iran_mirrors=False,
            )
            project_dir = Path(tmpdir)
            write_all(config, project_dir)

            # Verify files exist
            assert (project_dir / ".env").exists()
            assert (project_dir / "docker-compose.yml").exists()
            assert (project_dir / STATE_FILE).exists()
            assert (project_dir / DATA_DIR).is_dir()
            assert (project_dir / DATA_DIR / "query_ip_allowlist.txt").exists()

            # Load and verify roundtrip
            loaded = load_config(project_dir)
            assert loaded is not None
            assert loaded.server_name == "testuser"
            assert loaded.music_bot_enabled is True
            assert loaded.melodify_api_key == "testkey"
            assert loaded.template_name == "neon_arena"
            assert loaded.iran_mirrors is False

    def test_load_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_config(Path(tmpdir))
            assert result is None

    def test_data_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SetupConfig(server_name="test")
            write_all(config, Path(tmpdir))
            assert (Path(tmpdir) / DATA_DIR).is_dir()

    def test_allowlist_contents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SetupConfig(server_name="test")
            write_all(config, Path(tmpdir))
            content = (Path(tmpdir) / DATA_DIR / "query_ip_allowlist.txt").read_text()
            assert "127.0.0.1" in content
            assert "172." in content
