from __future__ import annotations

import re

import lavalink

BAD_WORDS = ("live", "cover")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def pick_recommendation(
    last_track: lavalink.AudioTrack, candidates: list[lavalink.AudioTrack]
) -> lavalink.AudioTrack | None:
    if not candidates:
        return None

    last_title = _normalize(last_track.title)
    for track in candidates:
        title = _normalize(track.title)
        if track.identifier == last_track.identifier:
            continue
        if track.duration < 30_000:
            continue
        if any(word in title for word in BAD_WORDS):
            continue
        if title == last_title:
            continue
        return track
    return None
