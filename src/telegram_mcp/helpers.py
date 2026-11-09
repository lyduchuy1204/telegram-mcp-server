"""Pure helpers that convert Telethon objects into plain JSON-friendly dicts."""

from __future__ import annotations

from datetime import datetime

from telethon import types, utils

MAX_TEXT = 2000
TELEGRAM_SERVICE_USER_ID = 777000


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def entity_kind(entity) -> str:
    """Classify an entity as user, bot, group, channel or inaccessible."""
    if isinstance(entity, types.User):
        return "bot" if entity.bot else "user"
    if isinstance(entity, types.Chat):
        return "group"
    if isinstance(entity, types.Channel):
        return "group" if entity.megagroup else "channel"
    if isinstance(entity, (types.ChatForbidden, types.ChannelForbidden)):
        return "inaccessible"
    return "unknown"


def is_stranger(entity) -> bool:
    """A real person you chat with privately who is not in your contacts."""
    return (
        isinstance(entity, types.User)
        and not entity.bot
        and not entity.contact
        and not entity.is_self
        and not entity.deleted
        and entity.id != TELEGRAM_SERVICE_USER_ID
    )


def dialog_info(dialog) -> dict:
    entity = dialog.entity
    deleted = bool(getattr(entity, "deleted", False))
    creator = bool(getattr(entity, "creator", False))
    return {
        "id": dialog.id,
        "title": "Deleted Account" if deleted else dialog.name,
        "kind": entity_kind(entity),
        "username": getattr(entity, "username", None),
        "deleted_account": deleted,
        "is_contact": bool(getattr(entity, "contact", False)) if isinstance(entity, types.User) else None,
        "unread": dialog.unread_count,
        "archived": dialog.archived,
        "last_message_date": iso(dialog.date),
        "members": getattr(entity, "participants_count", None),
        "i_am_creator": creator,
        "i_am_admin": creator or bool(getattr(entity, "admin_rights", None)),
    }


def message_info(message) -> dict:
    text = message.message or ""
    sender = message.sender
    return {
        "id": message.id,
        "date": iso(message.date),
        "from_me": message.out,
        "sender": (utils.get_display_name(sender) if sender else None) or str(message.sender_id),
        "sender_id": message.sender_id,
        "text": text[:MAX_TEXT] + ("…" if len(text) > MAX_TEXT else ""),
        "media": type(message.media).__name__.removeprefix("MessageMedia") if message.media else None,
        "reply_to": message.reply_to_msg_id,
    }


def privacy_level(rules) -> dict:
    """Summarise Telegram privacy rules as everybody / contacts / nobody plus exceptions."""
    names = [type(r).__name__.removeprefix("PrivacyValue") for r in rules]
    if "AllowAll" in names:
        level = "everybody"
    elif "AllowContacts" in names:
        level = "contacts"
    else:
        level = "nobody"
    return {
        "level": level,
        "rules": names,
        "always_allow_users": sum(len(r.users) for r in rules if isinstance(r, types.PrivacyValueAllowUsers)),
        "never_allow_users": sum(len(r.users) for r in rules if isinstance(r, types.PrivacyValueDisallowUsers)),
    }


def normalize_phone(raw: str, default_country_code: str | None = None) -> str:
    """Return an international (+E.164-style) phone number.

    ``+44 20 7946 0000`` -> ``+442079460000``. Without a leading ``+`` the number is
    treated as local and ``default_country_code`` is prepended (a single leading 0 trunk
    prefix is dropped). Raises ValueError when the result cannot be international.
    """
    raw = raw.strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError("Phone number has no digits")
    if raw.startswith("+"):
        return "+" + digits
    if raw.startswith("00"):
        return "+" + digits[2:]
    if default_country_code:
        if digits.startswith(default_country_code) and len(digits) > len(default_country_code) + 6:
            return "+" + digits
        return "+" + default_country_code + digits.lstrip("0")
    raise ValueError(
        "Use international format with a leading + (e.g. +14155550100), or set TELEGRAM_DEFAULT_COUNTRY_CODE"
    )
