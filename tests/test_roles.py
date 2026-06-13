"""Tests for tschan.templates.roles"""

from tschan.templates.roles import ROLE_CATEGORIES, get_roles_for_groups


class TestRoleCategories:
    def test_staff_exists(self):
        assert "staff" in ROLE_CATEGORIES

    def test_staff_is_mandatory(self):
        assert ROLE_CATEGORIES["staff"]["mandatory"] is True

    def test_games_exists(self):
        assert "games" in ROLE_CATEGORIES

    def test_cozy_exists(self):
        assert "cozy" in ROLE_CATEGORIES

    def test_nerd_corner_exists(self):
        assert "nerd_corner" in ROLE_CATEGORIES

    def test_non_staff_not_mandatory(self):
        for key, cat in ROLE_CATEGORIES.items():
            if key != "staff":
                assert cat["mandatory"] is False

    def test_staff_roles(self):
        roles = ROLE_CATEGORIES["staff"]["roles"]
        assert "Dev" in roles
        assert "Admin" in roles
        assert "Mod" in roles
        assert "Member" in roles

    def test_games_roles(self):
        roles = ROLE_CATEGORIES["games"]["roles"]
        assert "Minecraft" in roles
        assert "Valorant" in roles
        assert "CS2" in roles

    def test_cozy_roles(self):
        roles = ROLE_CATEGORIES["cozy"]["roles"]
        assert "Chamomile Hours" in roles
        assert "Duvet Burrito" in roles

    def test_nerd_corner_roles(self):
        roles = ROLE_CATEGORIES["nerd_corner"]["roles"]
        assert "Terminal Goblin" in roles
        assert "Vim Escapee" in roles

    def test_all_categories_have_display_name(self):
        for cat in ROLE_CATEGORIES.values():
            assert "display" in cat
            assert len(cat["display"]) > 0

    def test_all_categories_have_roles(self):
        for cat in ROLE_CATEGORIES.values():
            assert "roles" in cat
            assert len(cat["roles"]) > 0


class TestGetRolesForGroups:
    def test_staff_only(self):
        roles = get_roles_for_groups(["staff"])
        role_names = [r["name"] for r in roles if not r.get("is_separator")]
        assert "Dev" in role_names
        assert "Admin" in role_names

    def test_staff_always_included(self):
        """Even if not explicitly listed, staff should be included."""
        roles = get_roles_for_groups(["games"])
        role_names = [r["name"] for r in roles if not r.get("is_separator")]
        assert "Dev" in role_names  # staff roles should be present

    def test_multiple_groups(self):
        roles = get_roles_for_groups(["staff", "games", "cozy"])
        role_names = [r["name"] for r in roles if not r.get("is_separator")]
        assert "Dev" in role_names
        assert "Minecraft" in role_names
        assert "Chamomile Hours" in role_names

    def test_separators_included(self):
        roles = get_roles_for_groups(["staff", "games"])
        separators = [r for r in roles if r.get("is_separator")]
        assert len(separators) >= 2  # At least Staff and Games separators

    def test_all_groups(self):
        roles = get_roles_for_groups(["staff", "games", "cozy", "nerd_corner"])
        role_names = [r["name"] for r in roles if not r.get("is_separator")]
        assert "Vim Escapee" in role_names
        assert "Steam Gamer" in role_names
