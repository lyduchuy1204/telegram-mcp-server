"""Interactive one-time login: ``telegram-mcp-login``.

Telegram sends the login code to your Telegram app (not by SMS). If two-step
verification is enabled you are asked for your cloud password as well. Nothing is
echoed back or written anywhere except the session file.
"""

from __future__ import annotations

import asyncio
import getpass
import sys

from telethon import TelegramClient

from .config import ConfigError, Settings, secure_session_location
from .helpers import normalize_phone


def _ask_phone(settings: Settings) -> str:
    while True:
        raw = input("Phone number (international format, e.g. +14155550100): ")
        try:
            phone = normalize_phone(raw, settings.default_country_code)
        except ValueError as exc:
            print(f"  {exc}")
            continue
        print(f"  Using {phone}")
        return phone


async def _login(settings: Settings) -> None:
    secure_session_location(settings.session_path)
    client = TelegramClient(settings.telethon_session, settings.api_id, settings.api_hash)
    await client.start(
        phone=lambda: _ask_phone(settings),
        password=lambda: getpass.getpass("Two-step verification password: "),
    )
    me = await client.get_me()
    await client.disconnect()
    secure_session_location(settings.session_path)
    handle = f"@{me.username}" if me.username else f"id {me.id}"
    print(f"\nLogged in as {me.first_name} ({handle}).")
    print(f"Session saved to {settings.session_path}")
    print("Keep this file private: anyone who has it can use your Telegram account.")


def main() -> None:
    try:
        settings = Settings.load()
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")
    asyncio.run(_login(settings))


if __name__ == "__main__":
    main()
