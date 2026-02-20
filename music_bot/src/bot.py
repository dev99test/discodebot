from __future__ import annotations

import logging
from typing import Literal

import discord
import pomice
from discord import app_commands
from discord.ext import commands

from config import AppConfig
from music.player import MusicPlayer
from music.ui import QueuePageView, SearchView

logger = logging.getLogger(__name__)


class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, player: MusicPlayer, config: AppConfig) -> None:
        self.bot = bot
        self.player = player
        self.config = config

    async def _player_for_interaction(self, interaction: discord.Interaction) -> pomice.Player:
        if interaction.guild is None:
            raise RuntimeError("길드에서만 사용할 수 있습니다.")

        vc = interaction.guild.voice_client
        if not isinstance(vc, pomice.Player):
            raise RuntimeError("봇이 음성 채널에 없습니다. /선수입장 을 먼저 사용하세요.")
        return vc

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player: pomice.Player, track, reason) -> None:
        if player.guild:
            await self.player.handle_track_end(player.guild.id, player)

    @app_commands.command(name="선수입장", description="내가 있는 음성 채널로 봇 입장")
    async def join_voice(self, interaction: discord.Interaction) -> None:
        try:
            await self.player.ensure_voice(interaction)
            await interaction.response.send_message("🎧 음성 채널에 입장했습니다.")
        except RuntimeError as exc:
            await interaction.response.send_message(f"❗ {exc}", ephemeral=True)

    @app_commands.command(name="나가", description="음성 채널 퇴장 + 큐 정리")
    async def leave_voice(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("길드에서만 사용할 수 있습니다.", ephemeral=True)
            return
        await self.player.leave(interaction.guild)
        await interaction.response.send_message("👋 음성 채널에서 나가고 큐를 정리했습니다.")

    @app_commands.command(name="검색", description="유튜브 검색 후 선택 메뉴로 큐 추가")
    @app_commands.describe(키워드="검색할 키워드")
    async def search(self, interaction: discord.Interaction, 키워드: str) -> None:
        await interaction.response.defer()
        try:
            active_player = await self.player.ensure_voice(interaction)
            tracks = await self.player.search_safe_tracks(키워드, self.config.bot.search_results)
            if not tracks:
                await interaction.followup.send("조건에 맞는 검색 결과가 없습니다.")
                return

            async def on_pick(pick_interaction: discord.Interaction, track) -> None:
                started = await self.player.enqueue_and_maybe_play(
                    pick_interaction.guild_id,
                    active_player,
                    track,
                )
                text = f"✅ 큐에 추가: **{getattr(track, 'title', '제목 없음')}**"
                if started:
                    text += "\n🎶 바로 재생을 시작합니다."
                await pick_interaction.response.send_message(text, ephemeral=True)

            await interaction.followup.send("원하는 곡을 선택하세요.", view=SearchView(tracks, on_pick))
        except RuntimeError as exc:
            await interaction.followup.send(f"❗ {exc}")

    @app_commands.command(name="재생", description="URL 또는 키워드로 재생")
    @app_commands.describe(입력="URL 또는 검색어")
    async def play(self, interaction: discord.Interaction, 입력: str) -> None:
        await interaction.response.defer()
        try:
            active_player = await self.player.ensure_voice(interaction)
            if 입력.startswith(("http://", "https://")):
                tracks = await self.player.search_tracks(입력)
            else:
                tracks = await self.player.search_safe_tracks(입력, 1)

            if not tracks:
                await interaction.followup.send("재생 가능한 곡을 찾지 못했습니다.")
                return

            for track in tracks:
                await self.player.enqueue_and_maybe_play(interaction.guild_id, active_player, track)

            if len(tracks) == 1:
                await interaction.followup.send(
                    f"🎵 재생 목록에 추가: **{getattr(tracks[0], 'title', '제목 없음')}**"
                )
            else:
                await interaction.followup.send(f"📚 플레이리스트 {len(tracks)}곡을 큐에 추가했습니다.")
        except RuntimeError as exc:
            await interaction.followup.send(f"❗ {exc}")

    @app_commands.command(name="스킵", description="현재 트랙 건너뛰기")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await self.player.skip(player)
        await interaction.response.send_message("⏭️ 다음 곡으로 넘겼습니다.")

    @app_commands.command(name="정지", description="일시정지")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await player.set_pause(True)
        await interaction.response.send_message("⏸️ 일시정지했습니다.")

    @app_commands.command(name="재개", description="재생 재개")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await player.set_pause(False)
        await interaction.response.send_message("▶️ 재생을 다시 시작합니다.")

    @app_commands.command(name="완전정지", description="정지 + 큐 비우기")
    async def stop_and_clear(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        await self.player.stop_clear(interaction.guild_id, player)
        await interaction.response.send_message("🛑 완전정지했습니다. 큐를 비웠습니다.")

    @app_commands.command(name="큐", description="현재 큐 보기")
    async def queue(self, interaction: discord.Interaction) -> None:
        page = 1
        text, max_page = await self.player.queue_page(interaction.guild_id, page)

        async def on_page(btn_interaction: discord.Interaction, next_page: int) -> None:
            nonlocal max_page
            next_text, max_page = await self.player.queue_page(interaction.guild_id, next_page)
            view = QueuePageView(next_page, max_page, on_page)
            await btn_interaction.response.edit_message(content=next_text, view=view)

        view = QueuePageView(page, max_page, on_page) if max_page > 1 else None
        await interaction.response.send_message(text, view=view)

    @app_commands.command(name="현재", description="현재 재생곡 + 실시간 프로그레스바")
    async def now_playing(self, interaction: discord.Interaction) -> None:
        player = await self._player_for_interaction(interaction)
        text = await self.player.now_playing_text(player)
        await interaction.response.send_message(text)
        msg = await interaction.original_response()

        state = await self.player.manager.get(interaction.guild_id)
        state.progress_message = msg
        await self.player.ensure_progress_task(interaction.guild_id, player)

    @app_commands.command(name="라디오", description="자동 유사곡 큐잉 on/off")
    @app_commands.describe(모드="on 또는 off")
    async def radio(self, interaction: discord.Interaction, 모드: Literal["on", "off"]) -> None:
        state = await self.player.manager.get(interaction.guild_id)
        state.radio_mode = 모드 == "on"
        if state.radio_mode:
            await interaction.response.send_message("📻 라디오 모드를 켰습니다.")
        else:
            await interaction.response.send_message("📴 라디오 모드를 껐습니다.")


class MusicBot(commands.Bot):
    def __init__(self, config: AppConfig) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.config_obj = config
        self.music: MusicPlayer | None = None

    async def setup_hook(self) -> None:
        self.music = MusicPlayer(self, self.config_obj)
        await self.music.setup_nodes()
        await self.add_cog(MusicCommands(self, self.music, self.config_obj))

        if self.config_obj.discord.test_guild_ids:
            for gid in self.config_obj.discord.test_guild_ids:
                guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            logger.info("테스트 길드 커맨드 동기화 완료")
        else:
            await self.tree.sync()
            logger.info("글로벌 커맨드 동기화 완료")

    async def close(self) -> None:
        if self.music:
            await self.music.close()
        await super().close()
