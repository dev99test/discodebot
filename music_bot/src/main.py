from __future__ import annotations

import asyncio
import shutil

from bot import MusicBot
from config import ConfigError, load_config
from logging_setup import setup_logging


def _check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit(
            "실행 오류: FFmpeg를 찾을 수 없습니다. README의 FFmpeg 설치 단계를 먼저 진행하세요."
        )


def main() -> None:
    setup_logging()
    _check_ffmpeg()

    try:
        config = load_config()
    except ConfigError as exc:
        raise SystemExit(f"설정 오류: {exc}") from exc

    bot = MusicBot(config)
    try:
        asyncio.run(bot.start(config.discord.token))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
