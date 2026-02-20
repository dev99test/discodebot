from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord
import pomice

from config import AppConfig
from music.guild_manager import GuildManager
from music.progress import render_progress
from music.recommend import is_safe_track, pick_recommendation
from utils.timefmt import format_ms

logger = logging.getLogger(__name__)


class MusicPlayer:
    def __init__(self, bot: discord.Client, config: AppConfig) -> None:
        self.bot = bot
        self.config = config
        self.manager = GuildManager()
        self.node_pool = pomice.NodePool()
        self._node_ready = False

    async def setup_nodes(self) -> None:
        if self._node_ready:
            return

        await self.node_pool.create_node(
            bot=self.bot,
            host=self.config.lavalink.host or "127.0.0.1",
            port=self.config.lavalink.port or 2333,
            password=self.config.lavalink.password or "youshallnotpass",
            identifier="MAIN",
        )
        self._node_ready = True

    async def close(self) -> None:
        return

    async def ensure_voice(self, interaction: discord.Interaction) -> pomice.Player:
        guild = interaction.guild
        if guild is None:
            raise RuntimeError("길드에서만 사용할 수 있습니다.")

        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None or member.voice is None or member.voice.channel is None:
            raise RuntimeError("먼저 음성 채널에 입장해주세요.")

        channel = member.voice.channel
        vc = guild.voice_client
        if vc is None:
            player = await channel.connect(cls=pomice.Player)
            assert isinstance(player, pomice.Player)
        else:
            if not isinstance(vc, pomice.Player):
                raise RuntimeError("현재 음성 클라이언트 타입이 올바르지 않습니다.")
            player = vc
            if vc.channel != channel:
                await vc.move_to(channel)

        if not hasattr(player, "queue"):
            player.queue = pomice.Queue()

        state = await self.manager.get(guild.id)
        state.text_channel_id = interaction.channel_id
        return player

    async def leave(self, guild: discord.Guild) -> None:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
        await self.manager.clear_state(guild.id)

    async def _search(self, query: str) -> list[Any]:
        if not self._node_ready:
            raise RuntimeError("Lavalink 노드가 준비되지 않았습니다.")

        search_query = query if query.startswith(("http://", "https://")) else f"ytsearch:{query}"
        node = self.node_pool.get_node()
        result = await node.get_tracks(search_query)

        if isinstance(result, list):
            return result
        tracks = getattr(result, "tracks", None)
        if tracks is None:
            return []
        return list(tracks)

    async def search_tracks(self, query: str) -> list[Any]:
        return await self._search(query)

    async def search_safe_tracks(self, query: str, limit: int) -> list[Any]:
        tracks = await self._search(query)
        return [t for t in tracks if is_safe_track(t)][:limit]

    async def enqueue_and_maybe_play(self, guild_id: int, player: pomice.Player, track: Any) -> bool:
        state = await self.manager.get(guild_id)
        async with state.lock:
            await state.queue.push(track)
            if not player.is_playing and not player.is_paused:
                await self._play_next(guild_id, player)
                return True
        return False

    async def _play_next(self, guild_id: int, player: pomice.Player) -> None:
        state = await self.manager.get(guild_id)
        next_track = await state.queue.pop_left()
        if next_track is None:
            return
        await player.play(next_track)
        await player.set_volume(self.config.bot.default_volume)
        state.last_track = next_track

    async def skip(self, player: pomice.Player) -> None:
        if player.is_playing:
            await player.stop()

    async def stop_clear(self, guild_id: int, player: pomice.Player) -> None:
        state = await self.manager.get(guild_id)
        async with state.lock:
            await state.queue.clear()
            await player.stop()

    async def queue_page(self, guild_id: int, page: int = 1, size: int = 10) -> tuple[str, int]:
        state = await self.manager.get(guild_id)
        items = await state.queue.snapshot()
        if not items:
            return "큐가 비어 있습니다.", 1

        max_page = (len(items) - 1) // size + 1
        page = min(max_page, max(1, page))
        start = (page - 1) * size
        end = start + size

        lines = [f"📜 큐 목록 (페이지 {page}/{max_page})"]
        for i, track in enumerate(items[start:end], start=start + 1):
            duration = int(getattr(track, "length", getattr(track, "duration", 0)))
            lines.append(
                f"{i}. {getattr(track, 'title', '제목 없음')} - {getattr(track, 'author', '알 수 없음')} ({format_ms(duration)})"
            )
        return "\n".join(lines), max_page

    async def now_playing_text(self, player: pomice.Player) -> str:
        current = getattr(player, "current", None)
        if not current:
            return "현재 재생 중인 곡이 없습니다."
        duration = int(getattr(current, "length", getattr(current, "duration", 0)))
        bar = render_progress(int(getattr(player, "position", 0)), duration)
        return f"🎵 현재 재생: **{getattr(current, 'title', '제목 없음')}**\n{bar}"

    async def ensure_progress_task(self, guild_id: int, player: pomice.Player) -> None:
        state = await self.manager.get(guild_id)
        if state.progress_task and not state.progress_task.done():
            return

        async def runner() -> None:
            while True:
                await asyncio.sleep(self.config.bot.progress_update_sec)
                if not getattr(player, "current", None) or not state.progress_message:
                    continue
                try:
                    await state.progress_message.edit(content=await self.now_playing_text(player))
                except discord.HTTPException:
                    logger.debug("진행바 메시지 갱신 실패", exc_info=True)

        state.progress_task = asyncio.create_task(runner(), name=f"progress-{guild_id}")

    async def handle_track_end(self, guild_id: int, player: pomice.Player) -> None:
        state = await self.manager.get(guild_id)
        async with state.lock:
            await self._play_next(guild_id, player)

            if not getattr(player, "current", None) and state.radio_mode and state.last_track:
                query = f"ytsearch:{getattr(state.last_track, 'title', '')} {getattr(state.last_track, 'author', '')}"
                tracks = await self._search(query)
                pick = pick_recommendation(state.last_track, tracks)
                if pick:
                    await state.queue.push(pick)
                    await self._play_next(guild_id, player)
                    channel_id = state.text_channel_id
                    if channel_id:
                        channel = self.bot.get_channel(channel_id)
                        if isinstance(channel, discord.TextChannel):
                            await channel.send(f"📻 라디오 모드 추천곡 추가: **{getattr(pick, 'title', '추천곡')}**")
