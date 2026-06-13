"""Channel template definitions for tschan.

Each template is a list of channel descriptors. Spacer channels use the TS3
``[cspacer{N}]`` naming convention to render as centred section separators.
Regular channels are prefixed with ``·`` for visual hierarchy.

Public API
----------
- ``get_template(name)`` — returns the channel list for a template key.
- ``get_template_names()`` — returns all valid template keys.
- ``get_template_preview(name)`` — returns a human-readable ASCII preview.
"""

from __future__ import annotations

from typing import Any

# ── Helpers ──────────────────────────────────────────────────────────────────


def _spacer(
    index: int,
    section: str,
    decorator: str,
) -> dict[str, Any]:
    """Build a spacer channel descriptor.

    TS3 renders ``[cspacer{N}]text`` as a centred, non-joinable separator.
    """
    return {
        "name": f"[cspacer{index}]━━━ {decorator} {section} {decorator} ━━━",
        "is_spacer": True,
        "section_name": section,
        "max_clients": None,
        "codec": 4,
        "codec_quality": 6,
    }


def _channel(
    name: str,
    *,
    max_clients: int | None = None,
    codec: int = 4,
    codec_quality: int = 6,
) -> dict[str, Any]:
    """Build a regular channel descriptor."""
    return {
        "name": f"· {name}",
        "is_spacer": False,
        "section_name": None,
        "max_clients": max_clients,
        "codec": codec,
        "codec_quality": codec_quality,
    }


# ── Template: meowers_hangout ────────────────────────────────────────────────

_MEOWERS_HANGOUT: list[dict[str, Any]] = [
    # Files
    _spacer(0, "Files", "✦"),
    _channel("Uploads"),
    # Hangout
    _spacer(1, "Hangout", "✦"),
    _channel("Welcome"),
    _channel("Living Room"),
    _channel("Late Night"),
    _channel("AFK"),
    # Tables
    _spacer(2, "Tables", "✦"),
    _channel("Duo Table", max_clients=2),
    _channel("Trio Table", max_clients=3),
    _channel("Squad Table", max_clients=4),
    _channel("Party Table", max_clients=5),
    # Private
    _spacer(3, "Private", "✦"),
    _channel("Quiet Room I"),
    _channel("Quiet Room II"),
    _channel("Quiet Room III"),
    _channel("Quiet Room IV"),
    # Staff
    _spacer(4, "Staff", "✦"),
    _channel("Staff Room"),
    _channel("Admin Room"),
    _channel("Owner Room"),
]

# ── Template: neon_arena ─────────────────────────────────────────────────────

_NEON_ARENA: list[dict[str, Any]] = [
    # Info
    _spacer(0, "Info", "⚡"),
    _channel("Patch Notes"),
    _channel("Rules"),
    # Lobby
    _spacer(1, "Lobby", "⚡"),
    _channel("Spawn Point"),
    _channel("Chill Zone"),
    _channel("Waiting Room"),
    _channel("AFK / Gone Dark"),
    # Squad Up
    _spacer(2, "Squad Up", "⚡"),
    _channel("Duo Queue", max_clients=2),
    _channel("Trio Queue", max_clients=3),
    _channel("Squad Queue", max_clients=4),
    _channel("Full Party", max_clients=5),
    # Ranked
    _spacer(3, "Ranked", "⚡"),
    _channel("Ranked Room I"),
    _channel("Ranked Room II"),
    _channel("Ranked Room III"),
    # Scrims
    _spacer(4, "Scrims", "⚡"),
    _channel("Scrim Bay I"),
    _channel("Scrim Bay II"),
    _channel("Scrim Bay III"),
    _channel("Scrim Bay IV"),
    # Ops
    _spacer(5, "Ops", "⚡"),
    _channel("Mod Station"),
    _channel("Admin Bunker"),
    _channel("Owner HQ"),
]

# ── Template: cozy_den ───────────────────────────────────────────────────────

_COZY_DEN: list[dict[str, Any]] = [
    # Notice Board
    _spacer(0, "Notice Board", "❀"),
    _channel("Uploads & Drops"),
    # Common Room
    _spacer(1, "Common Room", "❀"),
    _channel("Front Porch"),
    _channel("The Lounge"),
    _channel("Movie Night"),
    _channel("Late Hours"),
    _channel("AFK Corner"),
    # Booths
    _spacer(2, "Booths", "❀"),
    _channel("Booth for 2", max_clients=2),
    _channel("Booth for 3", max_clients=3),
    _channel("Booth for 4", max_clients=4),
    _channel("Booth for 5", max_clients=5),
    # Hideaways
    _spacer(3, "Hideaways", "❀"),
    _channel("Hideaway I"),
    _channel("Hideaway II"),
    _channel("Hideaway III"),
    _channel("Hideaway IV"),
    # Staff Only
    _spacer(4, "Staff Only", "❀"),
    _channel("Staff Lounge"),
    _channel("Mod Kitchen"),
    _channel("Owner's Den"),
]

# ── Registry ─────────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "meowers_hangout": _MEOWERS_HANGOUT,
    "neon_arena": _NEON_ARENA,
    "cozy_den": _COZY_DEN,
}


# ── Public API ───────────────────────────────────────────────────────────────


def get_template_names() -> list[str]:
    """Return all available template keys."""
    return list(_TEMPLATES.keys())


def get_template(name: str) -> list[dict[str, Any]]:
    """Return the channel list for the given template.

    Args:
        name: Template key (e.g. ``"meowers_hangout"``).

    Returns:
        A *copy* of the channel list so callers can't mutate the originals.

    Raises:
        KeyError: If *name* is not a known template.
    """
    if name not in _TEMPLATES:
        raise KeyError(
            f"Unknown template {name!r}. "
            f"Available: {', '.join(_TEMPLATES)}"
        )
    # Return a shallow copy — each inner dict is never mutated downstream.
    return list(_TEMPLATES[name])


def get_template_preview(name: str) -> str:
    """Return a human-readable ASCII preview of the channel tree.

    Spacer channels are rendered as decorated section headers. Regular
    channels are indented below them with a ``├──`` / ``└──`` tree guide.

    Args:
        name: Template key.

    Returns:
        Multi-line string suitable for terminal display.

    Raises:
        KeyError: If *name* is not a known template.
    """
    channels = get_template(name)
    lines: list[str] = []

    # Group channels by section for tree-style rendering.
    i = 0
    while i < len(channels):
        ch = channels[i]
        if ch["is_spacer"]:
            # Render the spacer as a section header.
            lines.append(f"  {ch['name']}")
            # Collect all non-spacer children that follow.
            children: list[dict[str, Any]] = []
            j = i + 1
            while j < len(channels) and not channels[j]["is_spacer"]:
                children.append(channels[j])
                j += 1
            for k, child in enumerate(children):
                connector = "└──" if k == len(children) - 1 else "├──"
                suffix = ""
                if child["max_clients"] is not None:
                    suffix = f"  [{child['max_clients']} max]"
                lines.append(f"      {connector} {child['name']}{suffix}")
            i = j
        else:
            # Orphan channel (shouldn't happen with well-formed templates).
            lines.append(f"    {ch['name']}")
            i += 1

    return "\n".join(lines)
