"""Account hygiene: profile, profile photo, privacy settings and "Log in with Telegram" sites."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from telethon import TelegramClient, functions, types

from ..app import DESTRUCTIVE, READ_ONLY, WRITE, client, tool
from ..helpers import iso, privacy_level

DRY_RUN_NOTE = "Nothing changed. Re-run with dry_run=false after the user confirms."

PRIVACY_KEYS = {
    "group_invites": types.InputPrivacyKeyChatInvite,  # who can add you to groups/channels
    "phone_calls": types.InputPrivacyKeyPhoneCall,
    "phone_number": types.InputPrivacyKeyPhoneNumber,
    "last_seen": types.InputPrivacyKeyStatusTimestamp,
    "profile_photo": types.InputPrivacyKeyProfilePhoto,
    "forwards": types.InputPrivacyKeyForwards,
}
PrivacySetting = Literal["group_invites", "phone_calls", "phone_number", "last_seen", "profile_photo", "forwards"]
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png")
MAX_PHOTO_BYTES = 10 * 1024 * 1024


# ---------- profile ----------


async def _profile(c: TelegramClient) -> dict:
    full = await c(functions.users.GetFullUserRequest("me"))
    me = full.users[0]
    return {
        "first_name": me.first_name or "",
        "last_name": me.last_name or "",
        "username": me.username,
        "about": full.full_user.about or "",
        "premium": bool(getattr(me, "premium", False)),
    }


@tool(READ_ONLY)
async def get_profile() -> dict:
    """Show the current profile: first/last name, @username and bio."""
    return await _profile(await client())


@tool(WRITE)
async def update_profile(
    first_name: str | None = None,
    last_name: str | None = None,
    about: str | None = None,
    username: str | None = None,
    dry_run: bool = True,
) -> dict:
    """Update name, bio and/or @username. Omitted fields stay unchanged; pass "" to clear
    last_name or about. Limits: names 64 chars, bio 70 (140 with Premium), username 5-32.
    Changing the username breaks old t.me/<old> links. dry_run=True previews and checks
    that the new username is available."""
    c = await client()
    before = await _profile(c)
    bio_max = 140 if before["premium"] else 70
    problems = []
    if first_name is not None and not 1 <= len(first_name) <= 64:
        problems.append("first_name must be 1-64 characters")
    if last_name is not None and len(last_name) > 64:
        problems.append("last_name must be at most 64 characters")
    if about is not None and len(about) > bio_max:
        problems.append(f"bio is {len(about)} characters, the limit is {bio_max}")
    available = None
    if username is not None:
        username = username.lstrip("@")
        if username.lower() != (before["username"] or "").lower():
            available = await c(functions.account.CheckUsernameRequest(username=username))
            if not available:
                problems.append(f"@{username} is taken or invalid")
    if problems:
        raise ValueError("; ".join(problems))

    after = {
        "first_name": before["first_name"] if first_name is None else first_name,
        "last_name": before["last_name"] if last_name is None else last_name,
        "about": before["about"] if about is None else about,
        "username": before["username"] if username is None else username,
    }
    info = {
        "before": before,
        "after": after,
        "bio_length": f"{len(after['about'])}/{bio_max}",
        "username_available": available,
    }
    if dry_run:
        return {"dry_run": True, **info, "note": DRY_RUN_NOTE}
    if first_name is not None or last_name is not None or about is not None:
        await c(functions.account.UpdateProfileRequest(first_name=first_name, last_name=last_name, about=about))
    if username is not None and username.lower() != (before["username"] or "").lower():
        await c(functions.account.UpdateUsernameRequest(username=username))
    return {"dry_run": False, **info, "now": await _profile(c)}


@tool(WRITE)
async def set_profile_photo(path: str, dry_run: bool = True) -> dict:
    """Upload a new profile photo from a local .jpg/.jpeg/.png file (max 10 MB).
    Previous photos stay in your photo history. dry_run=True only validates the file."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f"File not found: {p}")
    if p.suffix.lower() not in PHOTO_SUFFIXES:
        raise ValueError("Only .jpg, .jpeg and .png files are supported")
    size = p.stat().st_size
    if size > MAX_PHOTO_BYTES:
        raise ValueError("The file is larger than 10 MB")
    c = await client()
    info = {
        "file": p.name,
        "size_kb": round(size / 1024, 1),
        "photos_before": (await c.get_profile_photos("me", limit=1)).total,
    }
    if dry_run:
        return {"dry_run": True, **info, "note": DRY_RUN_NOTE}
    await c(functions.photos.UploadProfilePhotoRequest(file=await c.upload_file(str(p))))
    return {"dry_run": False, **info, "photos_now": (await c.get_profile_photos("me", limit=1)).total}


# ---------- privacy ----------


@tool(READ_ONLY)
async def get_privacy() -> dict:
    """Show privacy levels (everybody / contacts / nobody) for group invites, calls,
    phone number, last seen, profile photo and forwards."""
    c = await client()
    out = {}
    for name, key in PRIVACY_KEYS.items():
        r = await c(functions.account.GetPrivacyRequest(key=key()))
        out[name] = privacy_level(r.rules)
    return out


@tool(WRITE)
async def set_privacy(
    setting: PrivacySetting, level: Literal["everybody", "contacts", "nobody"], dry_run: bool = True
) -> dict:
    """Change one privacy setting; per-user exceptions are preserved.
    Recommended: group_invites=contacts so strangers cannot add you to spam groups."""
    c = await client()
    key = PRIVACY_KEYS[setting]
    current = await c(functions.account.GetPrivacyRequest(key=key()))
    before = privacy_level(current.rules)
    if dry_run:
        return {"dry_run": True, "setting": setting, "before": before, "after_level": level, "note": DRY_RUN_NOTE}

    rules: list = []
    for r in current.rules:  # keep "always allow" / "never allow" user exceptions
        if isinstance(r, types.PrivacyValueAllowUsers):
            rules.append(types.InputPrivacyValueAllowUsers(users=[await c.get_input_entity(u) for u in r.users]))
        elif isinstance(r, types.PrivacyValueDisallowUsers):
            rules.append(types.InputPrivacyValueDisallowUsers(users=[await c.get_input_entity(u) for u in r.users]))
    if level == "everybody":
        rules.append(types.InputPrivacyValueAllowAll())
    elif level == "contacts":
        rules += [types.InputPrivacyValueAllowContacts(), types.InputPrivacyValueDisallowAll()]
    else:
        rules.append(types.InputPrivacyValueDisallowAll())
    await c(functions.account.SetPrivacyRequest(key=key(), rules=rules))
    after = await c(functions.account.GetPrivacyRequest(key=key()))
    return {"dry_run": False, "setting": setting, "before": before, "now": privacy_level(after.rules)}


# ---------- "Log in with Telegram" websites ----------


@tool(READ_ONLY)
async def list_web_logins() -> list[dict]:
    """List websites you signed into with "Log in with Telegram"."""
    c = await client()
    r = await c(functions.account.GetWebAuthorizationsRequest())
    bots = {u.id: u for u in r.users}
    out = []
    for a in r.authorizations:
        bot = bots.get(a.bot_id)
        out.append(
            {
                "hash": str(a.hash),
                "domain": a.domain,
                "bot": f"@{bot.username}" if bot and bot.username else str(a.bot_id),
                "browser": a.browser,
                "platform": a.platform,
                "created": iso(a.date_created),
                "last_active": iso(a.date_active),
                "region": a.region,
            }
        )
    return out


@tool(DESTRUCTIVE)
async def revoke_web_logins(hashes: list[str], dry_run: bool = True) -> dict:
    """Sign out of "Log in with Telegram" websites (hashes come from list_web_logins)."""
    c = await client()
    r = await c(functions.account.GetWebAuthorizationsRequest())
    by_hash = {str(a.hash): a for a in r.authorizations}
    targets = [by_hash[h] for h in hashes if h in by_hash]
    plan = [{"hash": str(a.hash), "domain": a.domain} for a in targets]
    missing = [h for h in hashes if h not in by_hash]
    if dry_run:
        return {"dry_run": True, "plan": plan, "not_found": missing, "note": DRY_RUN_NOTE}
    for a in targets:
        await c(functions.account.ResetWebAuthorizationRequest(hash=a.hash))
    return {"dry_run": False, "revoked": plan, "not_found": missing}
