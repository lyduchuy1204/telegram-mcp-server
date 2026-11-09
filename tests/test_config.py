from pathlib import Path

import pytest

from telegram_mcp import config
from telegram_mcp.config import ConfigError, Settings, parse_env_file

VALID = {"TELEGRAM_API_ID": "12345", "TELEGRAM_API_HASH": "a" * 32}


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never read the developer's real ~/.telegram-mcp/.env or ./.env during tests."""
    monkeypatch.setattr(config, "DEFAULT_HOME", tmp_path / "home")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_MCP_ENV_FILE", raising=False)


def test_loads_valid_settings_with_secure_default_session_path():
    s = Settings.load(dict(VALID))
    assert s.api_id == 12345
    assert s.mode == "full"
    assert s.session_path.name == "telegram.session"
    assert s.session_path.parent == config.DEFAULT_HOME
    assert s.telethon_session.endswith("telegram")


@pytest.mark.parametrize("api_id", ["", "abc", "12a"])
def test_rejects_bad_api_id(api_id):
    with pytest.raises(ConfigError):
        Settings.load({**VALID, "TELEGRAM_API_ID": api_id})


@pytest.mark.parametrize("api_hash", ["", "short", "z" * 32, "a" * 31])
def test_rejects_bad_api_hash(api_hash):
    with pytest.raises(ConfigError):
        Settings.load({**VALID, "TELEGRAM_API_HASH": api_hash})


def test_rejects_unknown_mode():
    with pytest.raises(ConfigError):
        Settings.load({**VALID, "TELEGRAM_MCP_MODE": "yolo"})


def test_rejects_non_numeric_country_code():
    with pytest.raises(ConfigError):
        Settings.load({**VALID, "TELEGRAM_DEFAULT_COUNTRY_CODE": "US"})


def test_parse_env_file(tmp_path: Path):
    f = tmp_path / ".env"
    f.write_text('# comment\nexport TELEGRAM_API_ID=42\nTELEGRAM_API_HASH="abc"\n\nBROKEN LINE\n', encoding="utf-8")
    assert parse_env_file(f) == {"TELEGRAM_API_ID": "42", "TELEGRAM_API_HASH": "abc"}


def test_environment_overrides_env_file(tmp_path: Path, monkeypatch):
    env_file = tmp_path / "custom.env"
    env_file.write_text("TELEGRAM_API_ID=111\nTELEGRAM_API_HASH=" + "b" * 32 + "\n", encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_MCP_ENV_FILE", str(env_file))
    raw = config.load_raw_settings({"TELEGRAM_API_ID": "222"})
    assert raw["TELEGRAM_API_ID"] == "222"
    assert raw["TELEGRAM_API_HASH"] == "b" * 32
