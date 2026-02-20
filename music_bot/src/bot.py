from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import AppConfig
from music.player import MusicPlayer
from music.ui import SearchView

logger = logging.getLogger(__name__)


class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, player: MusicPlayer, config: AppConfig) -> None:
        self.bot = bot
        self.player = player
        self.config = config

    async def _player_for_interaction(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            raise RuntimeError("길드에서만 사용할 수 있습니다.")
        return self.player.lavalink.player_manager.create(interaction.guild_id)

    @app_commands.command(name="선수입장", description="내가 있는 음성 채널로 봇 입장")
    async def join_voice(self, interaction: discord.Interaction) -> None:
        try:
            await self.player.ensure_voice(interaction)
            await interaction.response.send_message("🎧 입장 완료! 같이 달려봅시다.")
        except RuntimeError as exc:
            await interaction.response.send_message(f"❗ {exc}", ephemeral=True)

    @app_commands.command(name="나가쇼", description="음성 채널 퇴장 + 큐 정리")
    async def leave_voice(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("길드에서만 사용할 수 있습니다.", ephemeral=True)
            return
        await self.player.leave(interaction.guild)
        await interaction.response.send_message("👋 퇴장 완료! 큐도 깨끗하게 정리했어요.")

    @app_commands.command(name="검색", description="유튜브 검색 후 드롭다운으로 선택")
    @app_commands.describe(키워드="검색할 키워드")
    async def search(self, interaction: discord.Interaction, 키워드: str) -> None:
        await interaction.response.defer()
        try:
            lavalink_player = await self.player.ensure_voice(interaction)
            tracks = await self.player.search_tracks(키워드)
            tracks = tracks[: self.config.bot.search_results]
            if not tracks:
                await interaction.followup.send("검색 결과가 없습니다.")
                return

            async def on_pick(pick_interaction: discord.Interaction, track):
                started = await self.player.enqueue_and_maybe_play(
                    pick_interaction.guild_id, lavalink_player, track
                )
                text = (
                    f"✅ 큐에 추가: **{track.title}**\n🎶 바로 재생 시작!"
                    if started
                    else f"✅ 큐에 추가: **{track.title}**"
                )
                await pick_interaction.response.send_message(text, ephemeral=True)

            view = SearchView(tracks, on_pick)
            await interaction.followup.send("원하는 곡을 선택하세요.", view=view)
        except RuntimeError as exc:
            await interaction.followup.send(f"❗ {exc}")

    @app_commands.command(name="재생", description="URL 또는 키워드로 재생")
    @app_commands.describe(입력="URL 또는 검색어")
    async def play(self, interaction: discord.Interaction, 입력: str) -> None:
        await interaction.response.defer()
        try:
            lavalink_player = await self.player.ensure_voice(interaction)
            tracks = await self.player.search_tracks(입력)
            if not tracks:
                await interaction.followup.send("재생 가능한 곡을 찾지 못했습니다.")
                return

            started_count = 0
            for track in tracks:
                started = await self.player.enqueue_and_maybe_play(
                    interaction.guild_id, lavalink_player, track
                )
                started_count += int(started)

            if len(tracks) == 1:
                await interaction.followup.send(f"🎵 추가 완료: **{tracks[0].title}**")
            else:
                await interaction.followup.send(
                    f"📚 플레이리스트 {len(tracks)}곡 추가 완료! (즉시 재생 시작 {started_count}회)"
                )
        except RuntimeError as exc:
            await interaction.followup.send(f"❗ {exc}")

    @app_commands.command(name="스킵", description="현재 곡 스킵")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await self.player.skip(interaction.guild_id, player)
        await interaction.response.send_message("⏭️ 스킵 완료!")

    @app_commands.command(name="정지", description="일시정지")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await player.set_pause(True)
        await interaction.response.send_message("⏸️ 일시정지 했습니다.")

    @app_commands.command(name="재개", description="재생 이어하기")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await player.set_pause(False)
        await interaction.response.send_message("▶️ 다시 재생합니다.")

    @app_commands.command(name="정지정지손들어움직이면쏜다", description="완전 정지 + 큐 비우기")
    async def stop_and_clear(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await self.player.stop_clear(interaction.guild_id, player)
        await interaction.response.send_message("🛑 완전 정지! 큐를 모두 비웠습니다.")

    @app_commands.command(name="큐", description="대기열 확인")
    @app_commands.describe(페이지="페이지 번호(기본 1)")
    async def queue(self, interaction: discord.Interaction, 페이지: int = 1) -> None:
        text = await self.player.queue_text(interaction.guild_id, 페이지)
        await interaction.response.send_message(text)

    @app_commands.command(name="현재", description="현재 재생곡 + 실시간 진행바")
    async def now_playing(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        text = await self.player.now_playing_text(player)
        await interaction.response.send_message(text)
        msg = await interaction.original_response()
        state = await self.player.manager.get(interaction.guild_id)
        state.progress_message = msg
        await self.player.ensure_progress_task(interaction, player)

    @app_commands.command(name="라디오", description="자동 추천 재생 모드")
    @app_commands.describe(모드="on 또는 off")
    async def radio(self, interaction: discord.Interaction, 모드: str) -> None:
        state = await self.player.manager.get(interaction.guild_id)
        mode_value = 모드.lower().strip()
        if mode_value not in {"on", "off"}:
            await interaction.response.send_message("모드는 on/off 중 하나로 입력해주세요.", ephemeral=True)
            return

        state.radio_mode = mode_value == "on"
        msg = "📻 라디오 모드 ON! 비슷한 곡을 자동 추천합니다." if state.radio_mode else "📴 라디오 모드 OFF"
        await interaction.response.send_message(msg)


class MusicBot(commands.Bot):
    def __init__(self, config: AppConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(command_prefix="!", intents=intents)
        self.config_obj = config
        self.music: MusicPlayer | None = None

    async def setup_hook(self) -> None:
        self.music = MusicPlayer(self, self.config_obj)
        await self.add_cog(MusicCommands(self, self.music, self.config_obj))

        if self.config_obj.discord.guild_ids:
            for gid in self.config_obj.discord.guild_ids:
                guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            logger.info("길드 전용 커맨드 동기화 완료")
        else:
            await self.tree.sync()
            logger.info("글로벌 커맨드 동기화 완료")

    async def on_socket_response(self, payload):
        if self.music:
            await self.music.voice_update_handler(payload)

    async def close(self) -> None:
        if self.music:
            await self.music.close()
        await super().close()
