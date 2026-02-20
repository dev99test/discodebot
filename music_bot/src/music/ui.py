from __future__ import annotations

import discord
import lavalink


class SearchSelect(discord.ui.Select):
    def __init__(self, tracks: list[lavalink.AudioTrack], on_pick):
        options: list[discord.SelectOption] = []
        for idx, track in enumerate(tracks, start=1):
            options.append(
                discord.SelectOption(
                    label=f"{idx}. {track.title[:90]}",
                    description=f"{track.author[:90]} | {track.duration // 1000}s",
                    value=str(idx - 1),
                )
            )
        super().__init__(placeholder="재생할 곡을 선택하세요.", options=options, min_values=1, max_values=1)
        self._tracks = tracks
        self._on_pick = on_pick

    async def callback(self, interaction: discord.Interaction) -> None:
        idx = int(self.values[0])
        track = self._tracks[idx]
        await self._on_pick(interaction, track)


class SearchView(discord.ui.View):
    def __init__(self, tracks: list[lavalink.AudioTrack], on_pick):
        super().__init__(timeout=60)
        self.add_item(SearchSelect(tracks, on_pick))
