# Security Policy

## Supported versions

Only the latest release on the `main` branch receives security fixes.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through
[GitHub Security Advisories](https://github.com/lyduchuy1204/telegram-mcp-server/security/advisories/new).
Include steps to reproduce, the impact, and the affected version or commit.

You can expect an acknowledgement within 72 hours and a fix or mitigation plan within 14 days for
confirmed issues.

**Never include** your `api_hash`, session file, login codes or message content in a report.

## Threat model

| Asset | Risk | Mitigation |
|---|---|---|
| Session file | Full account takeover if copied | Stored in `~/.telegram-mcp/`, `0600` on POSIX, git-ignored, never logged |
| `api_hash` | Abuse of your API app quota | Read from env or `.env` only, validated, git-ignored |
| Destructive actions | Accidental mass deletion triggered by the model | `dry_run=True` default, permission modes, MCP client approvals |
| Prompt injection via messages | Model follows instructions hidden in chats | Server instructions mark message content as untrusted; destructive tools still need confirmation |
| Supply chain | Malicious dependency update | Bounded version ranges, Dependabot alerts, CI secret scanning |

## If your session leaks

1. In Telegram, open **Settings → Devices** and terminate the unknown session (or **Terminate all other sessions**).
2. Delete the local session file and log in again.
3. Rotate nothing else: the session is independent of your `api_hash`, but you may also delete and
   recreate the app on my.telegram.org.
