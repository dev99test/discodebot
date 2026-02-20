from __future__ import annotations


def format_ms(ms: int) -> str:
    total = max(0, int(ms // 1000))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
