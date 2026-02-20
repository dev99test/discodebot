from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import discord


from utils.timefmt import format_ms

OnTrackPicked = Callable[[discord.Interaction, Any], Coroutine[Any, Any, None]]

OnPageChange = Callable[[discord.Interaction, int], Coroutine[Any, Any, None]]


class SearchSelect(discord.ui.Select):

    def __init__(self, tracks: list[Any], on_pick: OnTrackPicked):
        options = [
            discord.SelectOption(
                label=f"{idx}. {getattr(track, 'title', '제목 없음')[:90]}",
                description=f"{getattr(track, 'author', '알 수 없음')[:50]} | {format_ms(int(getattr(track, 'length', getattr(track, 'duration', 0))))}",

                value=str(idx - 1),
            )
            for idx, track in enumerate(tracks, start=1)
        ]
        super().__init__(placeholder="재생할 곡을 선택하세요.", options=options, min_values=1, max_values=1)
        self._tracks = tracks
        self._on_pick = on_pick

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_pick(interaction, self._tracks[int(self.values[0])])


class SearchView(discord.ui.View):

    def __init__(self, tracks: list[Any], on_pick: OnTrackPicked):

        super().__init__(timeout=60)
        self.add_item(SearchSelect(tracks, on_pick))


class QueuePageView(discord.ui.View):
    def __init__(self, page: int, max_page: int, on_page: OnPageChange):
        super().__init__(timeout=120)
        self.page = page
        self.max_page = max_page
        self._on_page = on_page

    async def _move(self, interaction: discord.Interaction, delta: int) -> None:
        next_page = min(self.max_page, max(1, self.page + delta))
        self.page = next_page
        await self._on_page(interaction, next_page)

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._move(interaction, -1)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._move(interaction, 1)
