from __future__ import annotations

import pytest

from melodify_ts_bot.duration_parser import DurationParseError, parse_duration_seconds


def test_parse_duration_seconds_valid_values() -> None:
    assert parse_duration_seconds("45s") == 45
    assert parse_duration_seconds("2m") == 120
    assert parse_duration_seconds("1h") == 3600
    assert parse_duration_seconds("1d") == 86400


@pytest.mark.parametrize("value", ["", "abc", "0h", "9w", "999d"])
def test_parse_duration_seconds_invalid_values(value: str) -> None:
    with pytest.raises(DurationParseError):
        parse_duration_seconds(value)
