import pytest
from telethon import types

from telegram_mcp.helpers import entity_kind, is_stranger, normalize_phone, privacy_level


@pytest.mark.parametrize(
    ("raw", "country", "expected"),
    [
        ("+1 (415) 555-0100", None, "+14155550100"),
        ("0044 20 7946 0000", None, "+442079460000"),
        ("4155550100", "1", "+14155550100"),
        ("020 7946 0000", "44", "+442079460000"),
        ("442079460000", "44", "+442079460000"),
    ],
)
def test_normalize_phone(raw, country, expected):
    assert normalize_phone(raw, country) == expected


@pytest.mark.parametrize("raw", ["", "abc", "4155550100"])
def test_normalize_phone_requires_country_or_plus(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw, None)


def _user(**kw):
    defaults = {"id": 1, "bot": False, "contact": False, "is_self": False, "deleted": False}
    return types.User(**{**defaults, **kw})


def test_entity_kind():
    assert entity_kind(_user()) == "user"
    assert entity_kind(_user(bot=True)) == "bot"
    assert entity_kind(types.ChatForbidden(id=1, title="x")) == "inaccessible"
    assert entity_kind(object()) == "unknown"


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({}, True),
        ({"contact": True}, False),
        ({"bot": True}, False),
        ({"is_self": True}, False),
        ({"deleted": True}, False),
        ({"id": 777000}, False),  # Telegram service notifications
    ],
)
def test_is_stranger(kw, expected):
    assert is_stranger(_user(**kw)) is expected


def test_privacy_level():
    assert privacy_level([types.PrivacyValueAllowAll()])["level"] == "everybody"
    contacts = privacy_level(
        [types.PrivacyValueAllowUsers(users=[1, 2]), types.PrivacyValueAllowContacts(), types.PrivacyValueDisallowAll()]
    )
    assert contacts["level"] == "contacts"
    assert contacts["always_allow_users"] == 2
    assert privacy_level([types.PrivacyValueDisallowAll()])["level"] == "nobody"
