"""Role / server-group template definitions for tschan.

Role groups are logical categories of TS3 server groups.  Each category
contains a visual separator (displayed via a special group name) and a list
of concrete role names.

Public API
----------
- ``get_roles_for_groups(selected)`` — returns a flat list of dicts
  suitable for ``TS3QueryClient.create_server_groups``.
"""

from __future__ import annotations

from typing import Any

# ── Category Definitions ─────────────────────────────────────────────────────

ROLE_CATEGORIES: dict[str, dict[str, Any]] = {
    "staff": {
        "display": "━━━━ ✦ Staff ✦ ━━━━",
        "mandatory": True,
        "roles": ["Dev", "Admin", "Mod", "Member", "Guest"],
    },
    "games": {
        "display": "━━━━ ✦ Games ✦ ━━━━",
        "mandatory": False,
        "roles": [
            "Minecraft",
            "Dota 2",
            "CS2",
            "Valorant",
            "League",
            "Steam Gamer",
        ],
    },
    "cozy": {
        "display": "━━━━ ✦ Cozy ✦ ━━━━",
        "mandatory": False,
        "roles": [
            "Chamomile Hours",
            "Duvet Burrito",
            "Window Watcher",
            "Hearthside",
            "3am Wanderer",
            "Whisper Mode",
        ],
    },
    "nerd_corner": {
        "display": "━━━━ ✦ Nerd Corner ✦ ━━━━",
        "mandatory": False,
        "roles": [
            "Terminal Goblin",
            "Rubber Duck Debug",
            "Localhost Lurker",
            "Dark Mode Devotee",
            "Git Blame Survivor",
            "Vim Escapee",
        ],
    },
}


# ── Public API ───────────────────────────────────────────────────────────────


def get_all_category_keys() -> list[str]:
    """Return all known role category keys."""
    return list(ROLE_CATEGORIES.keys())


def get_mandatory_categories() -> list[str]:
    """Return category keys that are always included."""
    return [k for k, v in ROLE_CATEGORIES.items() if v["mandatory"]]


def get_roles_for_groups(selected: list[str]) -> list[dict[str, Any]]:
    """Build a flat list of group-separator + role entries for TS3 creation.

    Mandatory categories are always included even if not explicitly listed
    in *selected*.  Each entry is a dict with:

    - ``name`` (str): Display name for the server group.
    - ``is_separator`` (bool): ``True`` for visual category dividers.
    - ``category`` (str): The category key this entry belongs to.

    The list is ordered: separator → roles, separator → roles, …

    Args:
        selected: List of category keys the user chose (e.g.
            ``["staff", "games"]``).

    Returns:
        Flat list ready for ``TS3QueryClient.create_server_groups``.

    Raises:
        KeyError: If a key in *selected* is not a known category.
    """
    # Ensure mandatory categories are always present, preserving order.
    ordered: list[str] = []
    for key in get_mandatory_categories():
        if key not in ordered:
            ordered.append(key)
    for key in selected:
        if key not in ordered:
            ordered.append(key)

    result: list[dict[str, Any]] = []
    for key in ordered:
        if key not in ROLE_CATEGORIES:
            raise KeyError(
                f"Unknown role category {key!r}. "
                f"Available: {', '.join(ROLE_CATEGORIES)}"
            )
        cat = ROLE_CATEGORIES[key]
        # Separator entry
        result.append(
            {
                "name": cat["display"],
                "is_separator": True,
                "category": key,
            }
        )
        # Role entries
        for role_name in cat["roles"]:
            result.append(
                {
                    "name": role_name,
                    "is_separator": False,
                    "category": key,
                }
            )

    return result
