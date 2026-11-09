"""Entry point: ``telegram-mcp`` runs the MCP server over stdio."""

from __future__ import annotations

import logging
import sys

from .app import MODE, mcp
from .tools import account, chats, cleanup  # noqa: F401  (importing registers the tools)


def main() -> None:
    # stdout carries the MCP protocol; all logs must go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("telegram_mcp").info("starting in %s mode", MODE)
    mcp.run()


if __name__ == "__main__":
    main()
