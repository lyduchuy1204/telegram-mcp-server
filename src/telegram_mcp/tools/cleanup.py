"""Destructive cleanup tools. Every tool here defaults to dry_run=True and only
previews what would happen; it acts only when called again with dry_run=False."""

from __future__ import annotations

from telethon import functions, types, utils

from ..app import DESTRUCTIVE, client, resolve, tool
from ..helpers import entity_kind, message_info

DRY_RUN_NOTE = "Nothing changed. Re-run with dry_run=false after the user confirms."


@tool(DESTRUCTIVE)
async def delete_messages(chat: str, message_ids: list[int], revoke: bool = True, dry_run: bool = True) -> dict:
    """Delete specific messages. revoke=True deletes for everyone where Telegram allows it
    (your own messages, private chats, or groups where you are admin)."""
    c = await client()
    entity = await resolve(chat)
    found = [m for m in await c.get_messages(entity, ids=message_ids) if m is not None]
    result = {
        "chat": utils.get_display_name(entity),
        "messages": [message_info(m) for m in found],
        "not_found": sorted(set(message_ids) - {m.id for m in found}),
        "revoke": revoke,
    }
    if dry_run:
        return {"dry_run": True, **result, "note": DRY_RUN_NOTE}
    affected = await c.delete_messages(entity, [m.id for m in found], revoke=revoke)
    return {"dry_run": False, **result, "deleted_count": sum(a.pts_count for a in affected or [])}


@tool(DESTRUCTIVE)
async def delete_my_messages(chat: str, limit: int | None = None, revoke: bool = True, dry_run: bool = True) -> dict:
    """Delete messages YOU sent in a chat, newest first (limit=None means all of them)."""
    c = await client()
    entity = await resolve(chat)
    msgs = [m async for m in c.iter_messages(entity, from_user="me", limit=limit)]
    info = {"chat": utils.get_display_name(entity), "my_message_count": len(msgs), "revoke": revoke}
    if dry_run:
        return {"dry_run": True, **info, "sample": [message_info(m) for m in msgs[:5]], "note": DRY_RUN_NOTE}
    ids = [m.id for m in msgs]
    deleted = 0
    for i in range(0, len(ids), 100):
        for affected in await c.delete_messages(entity, ids[i : i + 100], revoke=revoke) or []:
            deleted += affected.pts_count
    return {"dry_run": False, **info, "deleted_count": deleted}


@tool(DESTRUCTIVE)
async def clear_chat_history(chat: str, for_everyone: bool = False, dry_run: bool = True) -> dict:
    """Wipe ALL messages in a chat but keep the chat in your list.

    Private chats, bots and small groups: cleared for you (for_everyone=True also clears the
    other side of a private chat). Supergroups: for_everyone needs admin rights.
    Broadcast channels cannot be cleared; use leave_or_delete_chats instead.
    """
    c = await client()
    entity = await resolve(chat)
    kind = entity_kind(entity)
    if isinstance(entity, types.Channel) and not entity.megagroup:
        raise ValueError("Broadcast channels cannot be cleared. Use leave_or_delete_chats instead.")
    total = (await c.get_messages(entity, limit=0)).total
    info = {"chat": utils.get_display_name(entity), "kind": kind, "message_count": total, "for_everyone": for_everyone}
    if dry_run:
        latest = [message_info(m) async for m in c.iter_messages(entity, limit=5)]
        return {"dry_run": True, **info, "latest_messages": latest, "note": DRY_RUN_NOTE}

    if isinstance(entity, types.Channel):  # supergroup
        await c(functions.channels.DeleteHistoryRequest(channel=entity, max_id=0, for_everyone=for_everyone))
    else:
        while True:  # Telegram deletes in batches; repeat until nothing is left
            r = await c(
                functions.messages.DeleteHistoryRequest(
                    peer=entity, max_id=0, just_clear=True, revoke=for_everyone and kind in ("user", "bot")
                )
            )
            if not r.offset:
                break
    return {"dry_run": False, **info, "cleared": True}


@tool(DESTRUCTIVE)
async def leave_or_delete_chats(chats: list[str], block_users: bool = False, dry_run: bool = True) -> dict:
    """Clean up junk chats in bulk.

    group / channel: leave it and remove it from your chat list.
    private chat / bot: delete the chat for you; block_users=True also blocks the user or bot.
    """
    c = await client()
    plan = []
    for chat in chats:
        entity = await resolve(chat)
        kind = entity_kind(entity)
        action = "leave" if kind in ("group", "channel") else "delete_chat"
        if block_users and kind in ("user", "bot"):
            action += "+block"
        plan.append(
            {
                "id": utils.get_peer_id(entity),
                "title": utils.get_display_name(entity),
                "kind": kind,
                "action": action,
                "i_am_creator": bool(getattr(entity, "creator", False)),
                "_entity": entity,
            }
        )

    def public(p: dict) -> dict:
        return {k: v for k, v in p.items() if not k.startswith("_")}

    if dry_run:
        owned = [p["title"] for p in plan if p["i_am_creator"]]
        return {
            "dry_run": True,
            "plan": [public(p) for p in plan],
            "warning": f"You created these; leaving does NOT delete them for members: {owned}" if owned else None,
            "note": DRY_RUN_NOTE,
        }

    done, failed = [], []
    for p in plan:
        try:
            await c.delete_dialog(p["_entity"])
            if "+block" in p["action"]:
                await c(functions.contacts.BlockRequest(id=p["_entity"]))
            done.append(public(p))
        except Exception as exc:  # report per-chat failures instead of aborting the batch
            failed.append({**public(p), "error": f"{type(exc).__name__}: {exc}"})
    return {"dry_run": False, "done": done, "failed": failed}
