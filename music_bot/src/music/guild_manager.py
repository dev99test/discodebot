from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import discord
import lavalink

from music.queue import AsyncQueue


@dataclass(slots=True)
class GuildState:
    guild_id: int
    queue: AsyncQueue = field(default_factory=AsyncQueue)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    radio_mode: bool = False
    progress_message: discord.Message | None = None
    progress_task: asyncio.Task | None = None
    text_channel_id: int | None = None
    last_track: lavalink.AudioTrack | None = None


class GuildManager:
    def __init__(self) -> None:
        self._states: dict[int, GuildState] = {}
        self._lock = asyncio.Lock()

    async def get(self, guild_id: int) -> GuildState:
        async with self._lock:
            if guild_id not in self._states:
                self._states[guild_id] = GuildState(guild_id=guild_id)
            return self._states[guild_id]

    async def clear_state(self, guild_id: int) -> None:
        state = await self.get(guild_id)
        await state.queue.clear()
        state.radio_mode = False
        if state.progress_task and not state.progress_task.done():
            state.progress_task.cancel()
        state.progress_task = None
        state.progress_message = None
        state.last_track = None
