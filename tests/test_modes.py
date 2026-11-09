"""The mode setting must hide write/destructive tools from the MCP client entirely."""

import asyncio
import importlib
import sys

import pytest

from telegram_mcp.app import DESTRUCTIVE, READ_ONLY, WRITE, is_allowed

READ_TOOLS = {
    "whoami",
    "list_chats",
    "read_messages",
    "search_messages",
    "get_profile",
    "get_privacy",
    "list_web_logins",
}
WRITE_TOOLS = {"send_message", "mark_as_read", "archive_chats", "update_profile", "set_profile_photo", "set_privacy"}
DESTRUCTIVE_TOOLS = {
    "delete_messages",
    "delete_my_messages",
    "clear_chat_history",
    "leave_or_delete_chats",
    "revoke_web_logins",
}


def test_is_allowed_matrix():
    assert all(is_allowed(a, "full") for a in (READ_ONLY, WRITE, DESTRUCTIVE))
    assert is_allowed(READ_ONLY, "safe") and is_allowed(WRITE, "safe") and not is_allowed(DESTRUCTIVE, "safe")
    assert is_allowed(READ_ONLY, "read-only")
    assert not is_allowed(WRITE, "read-only") and not is_allowed(DESTRUCTIVE, "read-only")


def _registered_tools(monkeypatch, mode: str) -> set[str]:
    monkeypatch.setenv("TELEGRAM_MCP_MODE", mode)
    for name in [m for m in sys.modules if m.startswith("telegram_mcp")]:
        del sys.modules[name]
    importlib.import_module("telegram_mcp.server")
    app = sys.modules["telegram_mcp.app"]
    return {t.name for t in asyncio.run(app.mcp.list_tools())}


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("full", READ_TOOLS | WRITE_TOOLS | DESTRUCTIVE_TOOLS),
        ("safe", READ_TOOLS | WRITE_TOOLS),
        ("read-only", READ_TOOLS),
    ],
)
def test_registered_tools_per_mode(monkeypatch, mode, expected):
    assert _registered_tools(monkeypatch, mode) == expected


def test_destructive_tools_default_to_dry_run():
    import inspect

    from telegram_mcp.tools import account, cleanup

    for fn in (
        cleanup.delete_messages,
        cleanup.delete_my_messages,
        cleanup.clear_chat_history,
        cleanup.leave_or_delete_chats,
        account.revoke_web_logins,
        account.update_profile,
        account.set_profile_photo,
        account.set_privacy,
    ):
        assert inspect.signature(fn).parameters["dry_run"].default is True, fn.__name__
