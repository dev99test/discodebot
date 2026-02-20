from __future__ import annotations

import asyncio
import logging

import discord
import lavalink
from lavalink.integrations.discord import LavalinkVoiceClient

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
        if bot.user is None:
            raise RuntimeError("봇 사용자 정보를 가져오지 못했습니다.")
        self.lavalink = lavalink.Client(bot.user.id)
        self._add_node()
        self.lavalink.add_event_hooks(self)

    def _add_node(self) -> None:
        self.lavalink.add_node(
            host=self.config.lavalink.host,
            port=self.config.lavalink.port,
            password=self.config.lavalink.password,
            region="asia",
            name="main",


        )

    async def close(self) -> None:
        await self.lavalink.close()

    async def voice_update_handler(self, data: dict) -> None:
        await self.lavalink.voice_update_handler(data)

    async def ensure_voice(self, interaction: discord.Interaction) -> lavalink.DefaultPlayer:
        guild = interaction.guild
        if guild is None:
            raise RuntimeError("길드에서만 사용할 수 있습니다.")

        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None or member.voice is None or member.voice.channel is None:
            raise RuntimeError("먼저 음성 채널에 입장해주세요.")

        vc = guild.voice_client
        if vc is None:
            await member.voice.channel.connect(cls=LavalinkVoiceClient)
        elif vc.channel != member.voice.channel:
            await vc.move_to(member.voice.channel)

        player = self.lavalink.player_manager.create(guild.id)
        state = await self.manager.get(guild.id)
        state.text_channel_id = interaction.channel_id
        return player

    async def leave(self, guild: discord.Guild) -> None:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
        await self.manager.clear_state(guild.id)

    async def search_tracks(self, query: str) -> list[lavalink.AudioTrack]:
        nodes = self.lavalink.node_manager.get_nodes()
        if not nodes:
            raise RuntimeError("Lavalink 노드에 연결되어 있지 않습니다.")

        node = nodes[0]
        search_query = query if query.startswith(("http://", "https://")) else f"ytsearch:{query}"
        result = await node.get_tracks(search_query)
        return result.get("tracks", [])

    async def search_safe_tracks(self, query: str, limit: int) -> list[lavalink.AudioTrack]:
        tracks = await self.search_tracks(query)
        filtered = [t for t in tracks if is_safe_track(t)]
        return filtered[:limit]

    async def enqueue_and_maybe_play(
        self,
        guild_id: int,
        player: lavalink.DefaultPlayer,
        track: lavalink.AudioTrack,
    ) -> bool:
        state = await self.manager.get(guild_id)
        async with state.lock:
            await state.queue.push(track)
            if not player.is_playing and not player.paused and not player.current:
                await self._play_next(guild_id, player)
                return True
        return False

    async def _play_next(self, guild_id: int, player: lavalink.DefaultPlayer) -> None:
        state = await self.manager.get(guild_id)
        next_track = await state.queue.pop_left()
        if next_track is None:
            return
        await player.play(next_track)
        await player.set_volume(self.config.bot.default_volume)

    async def skip(self, player: lavalink.DefaultPlayer) -> None:
        await player.stop()

    async def stop_clear(self, guild_id: int, player: lavalink.DefaultPlayer) -> None:
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
        sliced = items[start:end]

        lines = [f"📜 큐 목록 (페이지 {page}/{max_page})"]
        for i, track in enumerate(sliced, start=start + 1):
            lines.append(f"{i}. {track.title} - {track.author} ({format_ms(track.duration)})")
        return "\n".join(lines), max_page

    async def now_playing_text(self, player: lavalink.DefaultPlayer) -> str:
        if not player.current:
            return "현재 재생 중인 곡이 없습니다."
        bar = render_progress(player.position, player.current.duration)
        return f"🎵 현재 재생: **{player.current.title}**\n{bar}"

    async def ensure_progress_task(self, guild_id: int, player: lavalink.DefaultPlayer) -> None:
        state = await self.manager.get(guild_id)
        if state.progress_task and not state.progress_task.done():
            return

        async def runner() -> None:
            while True:
                await asyncio.sleep(self.config.bot.progress_update_sec)
                if not player.current or not state.progress_message:
                    continue
                try:
                    await state.progress_message.edit(content=await self.now_playing_text(player))
                except discord.HTTPException:
                    logger.debug("진행바 메시지 갱신 실패", exc_info=True)

        state.progress_task = asyncio.create_task(runner(), name=f"progress-{guild_id}")

    @lavalink.listener(lavalink.events.TrackStartEvent)
    async def on_track_start(self, event: lavalink.events.TrackStartEvent) -> None:
        state = await self.manager.get(event.player.guild_id)
        state.last_track = event.track

    @lavalink.listener(lavalink.events.TrackEndEvent)
    async def on_track_end(self, event: lavalink.events.TrackEndEvent) -> None:
        guild_id = event.player.guild_id
        state = await self.manager.get(guild_id)

        async with state.lock:
            await self._play_next(guild_id, event.player)

            if event.player.current is None and state.radio_mode and state.last_track:
                node = self.lavalink.node_manager.get_nodes()[0]
                query = f"ytsearch:{state.last_track.title} {state.last_track.author}"
                result = await node.get_tracks(query)
                pick = pick_recommendation(state.last_track, result.get("tracks", []))
                if pick:
                    await state.queue.push(pick)
                    await self._play_next(guild_id, event.player)
                    channel_id = state.text_channel_id
                    if channel_id:
                        channel = self.bot.get_channel(channel_id)
                        if isinstance(channel, discord.TextChannel):
                            await channel.send(f"📻 라디오 모드 추천곡 추가: **{pick.title}**")

    @lavalink.listener(lavalink.events.NodeDisconnectedEvent)
    async def on_node_disconnect(self, _: lavalink.events.NodeDisconnectedEvent) -> None:
        logger.warning("Lavalink 연결이 끊어졌습니다. 자동 재연결을 시도합니다.")
