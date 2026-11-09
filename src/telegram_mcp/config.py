"""Configuration loading.

Settings are read, in order of precedence, from:

1. process environment variables
2. the file named by ``TELEGRAM_MCP_ENV_FILE``
3. ``./.env`` in the current working directory
4. ``~/.telegram-mcp/.env``

The Telegram session file grants FULL access to your account. By default it is stored
outside any project folder, in ``~/.telegram-mcp/``, with owner-only permissions on
POSIX systems.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Mode = Literal["full", "safe", "read-only"]
MODES: tuple[Mode, ...] = ("full", "safe", "read-only")

DEFAULT_HOME = Path.home() / ".telegram-mcp"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a minimal KEY=VALUE .env file (comments and blank lines ignored)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_sources() -> list[Path]:
    sources = []
    if os.environ.get("TELEGRAM_MCP_ENV_FILE"):
        sources.append(Path(os.environ["TELEGRAM_MCP_ENV_FILE"]).expanduser())
    sources.append(Path.cwd() / ".env")
    sources.append(DEFAULT_HOME / ".env")
    return sources


def load_raw_settings(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Merge .env files and the environment (environment wins)."""
    merged: dict[str, str] = {}
    for source in reversed(_env_sources()):  # lowest precedence first
        merged.update(parse_env_file(source))
    merged.update(os.environ if environ is None else environ)
    return merged


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session_path: Path
    mode: Mode
    default_country_code: str | None

    @classmethod
    def load(cls, environ: dict[str, str] | None = None) -> Settings:
        raw = load_raw_settings(environ)

        api_id_raw = raw.get("TELEGRAM_API_ID", "").strip()
        api_hash = raw.get("TELEGRAM_API_HASH", "").strip()
        if not api_id_raw.isdigit():
            raise ConfigError("TELEGRAM_API_ID is missing or not a number. Get it at https://my.telegram.org")
        if len(api_hash) != 32 or not all(ch in "0123456789abcdef" for ch in api_hash.lower()):
            raise ConfigError("TELEGRAM_API_HASH is missing or malformed (expected 32 hex chars)")

        mode = raw.get("TELEGRAM_MCP_MODE", "full").strip().lower()
        if mode not in MODES:
            raise ConfigError(f"TELEGRAM_MCP_MODE must be one of {', '.join(MODES)}")

        session = raw.get("TELEGRAM_SESSION_PATH", "").strip()
        session_path = Path(session).expanduser() if session else DEFAULT_HOME / "telegram.session"

        country = raw.get("TELEGRAM_DEFAULT_COUNTRY_CODE", "").strip().lstrip("+") or None
        if country is not None and not country.isdigit():
            raise ConfigError("TELEGRAM_DEFAULT_COUNTRY_CODE must be digits, e.g. 1 or 44")

        return cls(
            api_id=int(api_id_raw),
            api_hash=api_hash,
            session_path=session_path,
            mode=mode,  # type: ignore[arg-type]
            default_country_code=country,
        )

    @property
    def telethon_session(self) -> str:
        """Telethon expects the path without the ``.session`` suffix."""
        p = str(self.session_path)
        return p[: -len(".session")] if p.endswith(".session") else p


def secure_session_location(session_path: Path) -> None:
    """Create the session directory and restrict permissions to the current user (POSIX)."""
    directory = session_path.parent
    directory.mkdir(parents=True, exist_ok=True)
    if os.name != "posix":
        return  # Windows: the user profile folder is already per-user by default
    os.chmod(directory, stat.S_IRWXU)  # 0700
    for candidate in (session_path, Path(str(session_path) + "-journal")):
        if candidate.exists():
            os.chmod(candidate, stat.S_IRUSR | stat.S_IWUSR)  # 0600
