from __future__ import annotations

import re
from typing import Any

BLOCK_WORDS = ("live", "cover")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_safe_track(track: Any) -> bool:
    title = _normalize(getattr(track, "title", ""))
    duration = int(getattr(track, "length", getattr(track, "duration", 0)))
    if duration < 30_000:
        return False
    if any(word in title for word in BLOCK_WORDS):
        return False
    return True


def pick_recommendation(last_track: Any, candidates: list[Any]) -> Any | None:
    last_title = _normalize(getattr(last_track, "title", ""))
    last_id = getattr(last_track, "track_id", getattr(last_track, "identifier", None))

    for track in candidates:
        curr_id = getattr(track, "track_id", getattr(track, "identifier", None))
        if last_id is not None and curr_id == last_id:
            continue
        if _normalize(getattr(track, "title", "")) == last_title:
            continue
        if not is_safe_track(track):
            continue
        return track
    return None
