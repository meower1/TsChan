"""CLI entry point for tschan."""

from __future__ import annotations

import argparse
import sys

from tschan.constants import VERSION


def main() -> int:
    """Main entry point for the tschan CLI.

    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(
        description="🌸 tschan — TeamSpeak 3 Template Generator",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the setup wizard (even if already configured)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tschan {VERSION}",
    )
    args = parser.parse_args()

    from tschan.tui.app import TschanApp

    app = TschanApp(force_setup=args.setup)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
