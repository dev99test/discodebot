from __future__ import annotations

import asyncio
import logging

import discord
import lavalink
from lavalink.integrations.discord import LavalinkVoiceClient

from config import AppConfig
from music.guild_manager import GuildManager
from music.progress import render_progress
from music.recommend import pick_recommendation
from utils.timefmt import format_ms

logger = logging.getLogger(__name__)


class MusicPlayer:
    def __init__(self, bot: discord.Client, config: AppConfig) -> None:
        self.bot = bot
        self.config = config
        self.manager = GuildManager()
        self.lavalink = lavalink.Client(bot.user.id)  # type: ignore[arg-type]
        self.lavalink.add_node(
            host=config.lavalink.host,
            port=config.lavalink.port,
            password=config.lavalink.password,
            region="asia",
            name="main",
            ssl=config.lavalink.use_ssl,
        )
        self.lavalink.add_event_hooks(self)

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
        player.store("channel", interaction.channel_id)
        state = await self.manager.get(guild.id)
        state.text_channel_id = interaction.channel_id
        return player

    async def leave(self, guild: discord.Guild) -> None:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
        await self.manager.clear_state(guild.id)

    async def search_tracks(self, query: str) -> list[lavalink.AudioTrack]:
        node = self.lavalink.node_manager.get_nodes()[0]
        if query.startswith("http://") or query.startswith("https://"):
            result = await node.get_tracks(query)
        else:
            result = await node.get_tracks(f"ytsearch:{query}")

        load_type = result.get("loadType")
        tracks = result.get("tracks", [])
        if load_type == "playlist":
            return tracks
        return tracks

    async def enqueue_and_maybe_play(
        self, guild_id: int, player: lavalink.DefaultPlayer, track: lavalink.AudioTrack
    ) -> bool:
        state = await self.manager.get(guild_id)
        await state.queue.push(track)
        if not player.is_playing and not player.paused:
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

    async def skip(self, guild_id: int, player: lavalink.DefaultPlayer) -> None:
        await player.stop()

    async def stop_clear(self, guild_id: int, player: lavalink.DefaultPlayer) -> None:
        state = await self.manager.get(guild_id)
        await state.queue.clear()
        await player.stop()

    async def queue_text(self, guild_id: int, page: int = 1, size: int = 10) -> str:
        state = await self.manager.get(guild_id)
        items = await state.queue.snapshot()
        if not items:
            return "큐가 비어 있습니다."

        page = max(1, page)
        start = (page - 1) * size
        end = start + size
        sliced = items[start:end]
        if not sliced:
            return "해당 페이지에 표시할 곡이 없습니다."

        lines = [f"📜 큐 목록 (페이지 {page})"]
        for i, track in enumerate(sliced, start=start + 1):
            lines.append(f"{i}. {track.title} - {track.author} ({format_ms(track.duration)})")
        return "\n".join(lines)

    async def now_playing_text(self, player: lavalink.DefaultPlayer) -> str:
        if not player.current:
            return "현재 재생 중인 곡이 없습니다."
        bar = render_progress(player.position, player.current.duration)
        return f"🎵 현재 곡: {player.current.title}\n{bar}"

    async def ensure_progress_task(
        self, interaction: discord.Interaction, player: lavalink.DefaultPlayer
    ) -> None:
        state = await self.manager.get(interaction.guild_id)
        if state.progress_task and not state.progress_task.done():
            return

        async def runner() -> None:
            while True:
                await asyncio.sleep(self.config.bot.progress_update_sec)
                if not player.current or not state.progress_message:
                    continue
                try:
                    text = await self.now_playing_text(player)
                    await state.progress_message.edit(content=text)
                except discord.HTTPException:
                    logger.debug("진행바 메시지 수정 실패", exc_info=True)

        state.progress_task = asyncio.create_task(runner(), name=f"progress-{interaction.guild_id}")

    @lavalink.listener(lavalink.events.TrackStartEvent)
    async def on_track_start(self, event: lavalink.events.TrackStartEvent) -> None:
        state = await self.manager.get(event.player.guild_id)
        state.last_track = event.track

    @lavalink.listener(lavalink.events.TrackEndEvent)
    async def on_track_end(self, event: lavalink.events.TrackEndEvent) -> None:
        guild_id = event.player.guild_id
        state = await self.manager.get(guild_id)
        await self._play_next(guild_id, event.player)

        if event.player.current is None and state.radio_mode and state.last_track:
            query = f"ytsearch:{state.last_track.title} {state.last_track.author}"
            node = self.lavalink.node_manager.get_nodes()[0]
            result = await node.get_tracks(query)
            tracks = result.get("tracks", [])
            pick = pick_recommendation(state.last_track, tracks)
            if pick:
                await state.queue.push(pick)
                await self._play_next(guild_id, event.player)
                channel_id = state.text_channel_id
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if isinstance(channel, discord.TextChannel):
                        await channel.send(f"📻 라디오 모드 추천곡 추가: **{pick.title}**")
