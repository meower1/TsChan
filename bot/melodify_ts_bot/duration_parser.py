from __future__ import annotations

import re

_DURATION_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[smhdSMHD])$")
_MAX_SECONDS = 7 * 24 * 60 * 60


class DurationParseError(ValueError):
    pass


def parse_duration_seconds(raw: str) -> int:
    value = raw.strip()
    match = _DURATION_RE.match(value)
    if match is None:
        raise DurationParseError("Duration must match <number><s|m|h|d>, e.g. 30m or 1h")

    amount = int(match.group("value"))
    if amount <= 0:
        raise DurationParseError("Duration must be greater than zero")

    unit = match.group("unit").lower()
    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }[unit]
    total = amount * multiplier
    if total > _MAX_SECONDS:
        raise DurationParseError("Duration cannot be more than 7d")

    return total
