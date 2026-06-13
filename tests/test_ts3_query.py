"""Tests for tschan.engine.ts3_query"""

from tschan.engine.ts3_query import TS3QueryClient


class TestTS3Escape:
    def test_escape_space(self):
        assert TS3QueryClient.ts3_escape("hello world") == r"hello\sworld"

    def test_escape_backslash(self):
        assert TS3QueryClient.ts3_escape("a\\b") == "a\\\\b"

    def test_escape_pipe(self):
        assert TS3QueryClient.ts3_escape("a|b") == r"a\pb"

    def test_escape_forward_slash(self):
        assert TS3QueryClient.ts3_escape("a/b") == r"a\/b"

    def test_no_escape_needed(self):
        assert TS3QueryClient.ts3_escape("hello") == "hello"

    def test_escape_multiple(self):
        result = TS3QueryClient.ts3_escape("hello world|test")
        assert r"\s" in result
        assert r"\p" in result


class TestTS3Unescape:
    def test_unescape_space(self):
        assert TS3QueryClient.ts3_unescape(r"hello\sworld") == "hello world"

    def test_unescape_pipe(self):
        assert TS3QueryClient.ts3_unescape(r"a\pb") == "a|b"

    def test_unescape_backslash(self):
        assert TS3QueryClient.ts3_unescape("a\\\\b") == "a\\b"

    def test_unescape_forward_slash(self):
        assert TS3QueryClient.ts3_unescape(r"a\/b") == "a/b"

    def test_roundtrip(self):
        original = "hello world|pipe/slash\\back"
        escaped = TS3QueryClient.ts3_escape(original)
        unescaped = TS3QueryClient.ts3_unescape(escaped)
        assert unescaped == original
