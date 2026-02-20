from __future__ import annotations

from utils.timefmt import format_ms


def render_progress(position_ms: int, duration_ms: int, blocks: int = 18) -> str:
    if duration_ms <= 0:
        return f"{format_ms(position_ms)} ┃{'░' * blocks}┃ ?:?? (0%)"

    ratio = max(0.0, min(1.0, position_ms / duration_ms))
    fill = int(ratio * blocks)
    bar = "█" * fill + "░" * (blocks - fill)
    pct = int(ratio * 100)
    return f"{format_ms(position_ms)} ┃{bar}┃ {format_ms(duration_ms)} ({pct}%)"
