from __future__ import annotations

import asyncio

from bot import MusicBot
from config import ConfigError, load_config
from logging_setup import setup_logging


def main() -> None:
    setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        raise SystemExit(f"설정 오류: {exc}") from exc

    bot = MusicBot(config)
    asyncio.run(bot.start(config.discord.token))


if __name__ == "__main__":
    main()
