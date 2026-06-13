"""Tests for tschan.models"""

from tschan.models import SetupConfig, _generate_token


class TestGenerateToken:
    def test_length(self):
        token = _generate_token(32)
        assert len(token) == 32

    def test_default_length(self):
        token = _generate_token()
        assert len(token) == 48

    def test_alphanumeric(self):
        token = _generate_token(100)
        assert token.isalnum()

    def test_uniqueness(self):
        tokens = {_generate_token(48) for _ in range(50)}
        assert len(tokens) == 50


class TestSetupConfig:
    def test_defaults(self):
        config = SetupConfig()
        assert config.server_name == ""
        assert config.music_bot_enabled is False
        assert config.template_name == "meowers_hangout"
        assert config.role_groups == ["staff"]
        assert len(config.query_password) == 48
        assert len(config.debug_token) == 48

    def test_auto_generated_passwords_unique(self):
        c1 = SetupConfig()
        c2 = SetupConfig()
        assert c1.query_password != c2.query_password
        assert c1.debug_token != c2.debug_token

    def test_validate_empty_name(self):
        config = SetupConfig(server_name="")
        errors = config.validate()
        assert any("Server name" in e for e in errors)

    def test_validate_valid(self):
        config = SetupConfig(server_name="meower")
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_music_bot_no_key(self):
        config = SetupConfig(
            server_name="test",
            music_bot_enabled=True,
            melodify_api_key="",
        )
        errors = config.validate()
        assert any("Melodify" in e or "API key" in e for e in errors)

    def test_validate_music_bot_with_key(self):
        config = SetupConfig(
            server_name="test",
            music_bot_enabled=True,
            melodify_api_key="abc123",
        )
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_bad_template(self):
        config = SetupConfig(
            server_name="test",
            template_name="nonexistent",
        )
        errors = config.validate()
        assert any("template" in e.lower() for e in errors)
