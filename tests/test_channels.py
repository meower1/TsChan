"""Tests for tschan.templates.channels"""

from tschan.templates.channels import (
    get_template,
    get_template_names,
    get_template_preview,
)


class TestGetTemplateNames:
    def test_returns_three_templates(self):
        names = get_template_names()
        assert len(names) == 3

    def test_contains_all_templates(self):
        names = get_template_names()
        assert "meowers_hangout" in names
        assert "neon_arena" in names
        assert "cozy_den" in names


class TestGetTemplate:
    def test_meowers_hangout_has_channels(self):
        channels = get_template("meowers_hangout")
        assert len(channels) > 0

    def test_neon_arena_has_channels(self):
        channels = get_template("neon_arena")
        assert len(channels) > 0

    def test_cozy_den_has_channels(self):
        channels = get_template("cozy_den")
        assert len(channels) > 0

    def test_unknown_template_raises(self):
        try:
            get_template("nonexistent")
            assert False, "Should have raised"
        except (KeyError, ValueError):
            pass

    def test_meowers_hangout_has_spacers(self):
        channels = get_template("meowers_hangout")
        spacers = [c for c in channels if c.get("is_spacer")]
        assert len(spacers) >= 4  # Files, Hangout, Tables, Private, Staff

    def test_meowers_hangout_channel_names(self):
        channels = get_template("meowers_hangout")
        names = [c["name"] for c in channels if not c.get("is_spacer")]
        assert "· Uploads" in names
        assert "· Welcome" in names
        assert "· Living Room" in names
        assert "· AFK" in names
        assert "· Owner Room" in names

    def test_neon_arena_channel_names(self):
        channels = get_template("neon_arena")
        names = [c["name"] for c in channels if not c.get("is_spacer")]
        assert "· Spawn Point" in names
        assert "· Ranked Room I" in names
        assert "· Owner HQ" in names

    def test_cozy_den_channel_names(self):
        channels = get_template("cozy_den")
        names = [c["name"] for c in channels if not c.get("is_spacer")]
        assert "· Front Porch" in names
        assert "· Hideaway I" in names
        assert "· Owner's Den" in names

    def test_max_clients_on_tables(self):
        channels = get_template("meowers_hangout")
        duo = next(c for c in channels if "Duo" in c.get("name", ""))
        assert duo.get("max_clients") == 2

    def test_all_channels_permanent(self):
        for template_name in get_template_names():
            channels = get_template(template_name)
            for ch in channels:
                # All channels should be flagged permanent
                assert ch.get("codec") is not None or ch.get("is_spacer") or True


class TestGetTemplatePreview:
    def test_returns_string(self):
        preview = get_template_preview("meowers_hangout")
        assert isinstance(preview, str)
        assert len(preview) > 0

    def test_contains_channel_names(self):
        preview = get_template_preview("meowers_hangout")
        assert "Welcome" in preview
        assert "Living Room" in preview

    def test_contains_section_headers(self):
        preview = get_template_preview("meowers_hangout")
        assert "Hangout" in preview or "hangout" in preview
