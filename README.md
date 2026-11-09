# Telegram MCP Server

[![CI](https://github.com/lyduchuy1204/telegram-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/lyduchuy1204/telegram-mcp-server/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-server-purple.svg)](https://modelcontextprotocol.io)

**A security-first [Model Context Protocol](https://modelcontextprotocol.io) server for your personal Telegram account.**
Let Claude Code, Claude Desktop, Cursor or any MCP client read your chats, clean up spam groups,
remove deleted-account chats and harden your privacy settings, using Telegram's official MTProto API
via [Telethon](https://github.com/LonamiWebs/Telethon).

Every destructive action is **dry-run by default**: the assistant has to show you a preview and get
your confirmation before anything is deleted, left or revoked.

---

## Contents

- [Why this server](#why-this-server)
- [Tools](#tools)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Connect your MCP client](#connect-your-mcp-client)
- [Configuration](#configuration)
- [Security model](#security-model)
- [Example prompts](#example-prompts)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Disclaimer](#disclaimer)

## Why this server

| | |
|---|---|
| **Dry-run by default** | Delete, leave, clear, block and revoke tools only preview until called with `dry_run=false`. |
| **Permission modes** | `full`, `safe` (no destructive tools) or `read-only`. Tools outside the mode are never exposed to the model. |
| **Session kept out of projects** | The login session lives in `~/.telegram-mcp/` with owner-only permissions (POSIX), not in your repo. |
| **Official API, small codebase** | MTProto through Telethon. No third-party relay, no telemetry, about 900 lines you can audit. |
| **Account cleanup built in** | Find deleted accounts, strangers, inaccessible groups and archived spam; bulk-leave with one confirmation. |
| **Prompt-injection aware** | Server instructions tell the model to treat message content as untrusted data. |
| **Flood-wait safe** | Telethon sleeps on `FloodWait` instead of hammering Telegram, which protects your account. |

## Tools

| Tool | Type | What it does |
|---|---|---|
| `whoami` | read | Show the logged-in account |
| `list_chats` | read | List chats with filters: `kind`, `archived`, `unread_only`, `deleted_accounts_only`, `strangers_only` |
| `read_messages` | read | Read recent messages in a chat, with paging |
| `search_messages` | read | Full-text search in one chat or across all chats |
| `get_profile` | read | Name, @username and bio |
| `get_privacy` | read | Privacy levels: group invites, calls, phone number, last seen, photo, forwards |
| `list_web_logins` | read | Websites you signed into with "Log in with Telegram" |
| `send_message` | write | Send a message as you |
| `mark_as_read` | write | Mark chats as read |
| `archive_chats` | write | Archive or unarchive chats (reversible) |
| `update_profile` | write, dry-run | Change name, bio and @username, with an availability check |
| `set_profile_photo` | write, dry-run | Upload a new profile photo (`.jpg`/`.png`, max 10 MB) |
| `set_privacy` | write, dry-run | Set a privacy rule to everybody, contacts or nobody, keeping per-user exceptions |
| `delete_messages` | destructive, dry-run | Delete specific messages |
| `delete_my_messages` | destructive, dry-run | Delete everything you sent in a chat |
| `clear_chat_history` | destructive, dry-run | Wipe a chat's history but keep the chat |
| `leave_or_delete_chats` | destructive, dry-run | Bulk-leave groups and channels, delete private chats, optionally block |
| `revoke_web_logins` | destructive, dry-run | Sign out of "Log in with Telegram" websites |

## Requirements

- Python 3.10+ and [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended)
- A Telegram account
- Your own API credentials from [my.telegram.org](https://my.telegram.org)

## Quick start

### 1. Get Telegram API credentials

1. Sign in at <https://my.telegram.org> and open **API development tools**.
2. Create an application (any name and platform).
3. Copy the **App api_id** and **App api_hash**.

> `api_hash` is a secret. Do not share it and do not commit it.

### 2. Store the credentials

```bash
mkdir -p ~/.telegram-mcp
curl -fsSL https://raw.githubusercontent.com/lyduchuy1204/telegram-mcp-server/main/.env.example -o ~/.telegram-mcp/.env
chmod 600 ~/.telegram-mcp/.env      # macOS / Linux
```

Edit `~/.telegram-mcp/.env`:

```dotenv
TELEGRAM_API_ID=1234567
TELEGRAM_API_HASH=your_32_character_api_hash
```

On Windows, create `%USERPROFILE%\.telegram-mcp\.env` with the same content.

### 3. Log in once

```bash
uvx --from git+https://github.com/lyduchuy1204/telegram-mcp-server telegram-mcp-login
```

Enter your phone number in international format (`+14155550100`), the code Telegram sends **to your
Telegram app**, and your two-step verification password if you have one. The session is saved to
`~/.telegram-mcp/telegram.session`.

<details>
<summary>Prefer a local clone?</summary>

```bash
git clone https://github.com/lyduchuy1204/telegram-mcp-server.git
cd telegram-mcp-server
uv sync
uv run telegram-mcp-login
```

Then use `uv --directory /absolute/path/to/telegram-mcp-server run telegram-mcp` as the server command below.
</details>

## Connect your MCP client

### Claude Code

```bash
claude mcp add telegram -- uvx --from git+https://github.com/lyduchuy1204/telegram-mcp-server telegram-mcp
```

Run `/mcp` inside Claude Code to check that `telegram` shows **connected**.

### Claude Desktop, Cursor, Windsurf and other clients

Add this to the client's MCP config (`claude_desktop_config.json`, `~/.cursor/mcp.json`, and so on):

```json
{
  "mcpServers": {
    "telegram": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/lyduchuy1204/telegram-mcp-server", "telegram-mcp"],
      "env": { "TELEGRAM_MCP_MODE": "safe" }
    }
  }
}
```

Credentials are read from `~/.telegram-mcp/.env`, so they do not need to be in the client config.

> Pin a release for reproducible installs: `git+https://github.com/lyduchuy1204/telegram-mcp-server@v0.1.0`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_API_ID` | required | From my.telegram.org |
| `TELEGRAM_API_HASH` | required | From my.telegram.org (32 hex characters) |
| `TELEGRAM_MCP_MODE` | `full` | `full`, `safe` (no destructive tools) or `read-only` |
| `TELEGRAM_SESSION_PATH` | `~/.telegram-mcp/telegram.session` | Where the login session is stored |
| `TELEGRAM_DEFAULT_COUNTRY_CODE` | none | Lets you type local numbers at login, e.g. `44` |
| `TELEGRAM_MCP_ENV_FILE` | none | Extra `.env` file to load |

Precedence: process environment, then `TELEGRAM_MCP_ENV_FILE`, then `./.env`, then `~/.telegram-mcp/.env`.

## Security model

> **The session file is equivalent to your logged-in Telegram app.** Anyone who copies it can read
> and send messages as you, without your password or 2FA.

What this project does to protect you:

- The session is stored **outside project folders**, by default in `~/.telegram-mcp/`, with `0700`/`0600`
  permissions on macOS and Linux, so it is not accidentally committed or synced.
- `.gitignore` blocks `.env`, `*.session`, MCP client configs and image files.
- **Least privilege:** choose `read-only` or `safe` mode when you only need to read or organise.
- **Two-step confirmation:** destructive tools return a preview first. The MCP client also asks
  you to approve each tool call unless you have allow-listed it.
- **Untrusted content:** the model is told never to follow instructions found inside Telegram messages.
- No logging of message contents, no network calls other than Telegram's own servers.

What you should do:

1. **Enable two-step verification** in Telegram (Settings → Privacy and Security).
2. Never paste your login code or session file into chats, issues or AI prompts.
3. Review **Settings → Devices** regularly. The MCP session shows up there and can be terminated at any time.
4. Do not run two server processes against the same session at once (Telegram may revoke it).
5. Revoke access quickly if a device is lost: terminate the session and delete `~/.telegram-mcp/telegram.session`.

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Example prompts

- "List my archived chats and tell me which ones look like spam."
- "Find chats with deleted accounts and remove them." The assistant previews first, then asks you.
- "Leave every 18+ or scam group I'm in, but keep anything work-related."
- "Who can add me to groups? Change it to contacts only."
- "Which websites did I log into with Telegram? Revoke the ones I haven't used this year."
- "Summarise unread messages in the AWS group from today."

## Troubleshooting

| Problem | Fix |
|---|---|
| `Not logged in. Run telegram-mcp-login first.` | Run the login step. Make sure the server and login use the same `TELEGRAM_SESSION_PATH`. |
| `PhoneNumberInvalidError` | Use international format with `+`, or set `TELEGRAM_DEFAULT_COUNTRY_CODE`. |
| `database is locked` | Another process is using the same session. Stop it, or point each process at its own session. |
| A tool is missing in the client | Check `TELEGRAM_MCP_MODE`; `safe` and `read-only` hide some tools. Reconnect the server after changing it. |
| Calls are slow | Telegram asked the client to wait (FloodWait). The server waits up to 120 s automatically. |

## Development

```bash
git clone https://github.com/lyduchuy1204/telegram-mcp-server.git
cd telegram-mcp-server
uv sync
uv run pytest          # unit tests, no Telegram account needed
uv run ruff check .    # lint and security rules (bandit)
```

Project layout:

```
src/telegram_mcp/
  config.py        settings, .env loading, session file permissions
  app.py           MCP server, Telegram client, permission-mode tool registration
  helpers.py       pure converters (chats, messages, privacy rules, phone numbers)
  login.py         interactive login CLI
  server.py        entry point
  tools/
    chats.py       read, search, send, mark read, archive
    cleanup.py     delete, clear, leave and block (dry-run by default)
    account.py     profile, photo, privacy and web logins
```

Contributions are welcome. Please open an issue first for larger changes.

## Disclaimer

This is an unofficial project and is not affiliated with Telegram. Automating a user account is
subject to the [Telegram API Terms of Service](https://core.telegram.org/api/terms). Use it on your
own account, at a human pace, and never for spam or bulk messaging.

## License

[MIT](LICENSE)
