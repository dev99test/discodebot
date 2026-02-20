from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class DiscordConfig:
    token: str
    guild_ids: list[int]


@dataclass(slots=True)
class LavalinkConfig:
    host: str
    port: int
    password: str
    use_ssl: bool


@dataclass(slots=True)
class BotConfig:
    default_volume: int
    progress_update_sec: int
    search_results: int


@dataclass(slots=True)
class AppConfig:
    discord: DiscordConfig
    lavalink: LavalinkConfig
    bot: BotConfig


class ConfigError(RuntimeError):
    pass


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ConfigError(f"config.yaml에 '{key}' 값이 없습니다.")
    return data[key]


def load_config(config_path: str | Path = "config.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(
            "config.yaml 파일이 없습니다. config.example.yaml을 복사해 config.yaml을 먼저 만드세요."
        )

    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}

    discord_raw = _require(data, "discord")
    lavalink_raw = _require(data, "lavalink")
    bot_raw = _require(data, "bot")

    discord_conf = DiscordConfig(
        token=str(_require(discord_raw, "token")),
        guild_ids=[int(x) for x in discord_raw.get("guild_ids", [])],
    )
    if not discord_conf.token:
        raise ConfigError("discord.token 값이 비어 있습니다.")

    lavalink_conf = LavalinkConfig(
        host=str(_require(lavalink_raw, "host")),
        port=int(_require(lavalink_raw, "port")),
        password=str(_require(lavalink_raw, "password")),
        use_ssl=bool(lavalink_raw.get("use_ssl", False)),
    )

    bot_conf = BotConfig(
        default_volume=max(1, min(1000, int(bot_raw.get("default_volume", 100)))),
        progress_update_sec=max(1, int(bot_raw.get("progress_update_sec", 2))),
        search_results=max(1, min(25, int(bot_raw.get("search_results", 10)))),
    )

    return AppConfig(discord=discord_conf, lavalink=lavalink_conf, bot=bot_conf)
