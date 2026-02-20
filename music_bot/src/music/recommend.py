from __future__ import annotations

import re

import lavalink

BLOCK_WORDS = ("live", "cover")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_safe_track(track: lavalink.AudioTrack) -> bool:
    title = _normalize(track.title)
    if track.duration < 30_000:
        return False
    if any(word in title for word in BLOCK_WORDS):
        return False
    return True


def pick_recommendation(
    last_track: lavalink.AudioTrack,
    candidates: list[lavalink.AudioTrack],
) -> lavalink.AudioTrack | None:
    last_title = _normalize(last_track.title)
    for track in candidates:
        if track.identifier == last_track.identifier:
            continue
        if _normalize(track.title) == last_title:
            continue
        if not is_safe_track(track):
            continue
        return track
    return None
