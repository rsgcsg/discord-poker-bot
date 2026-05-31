from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .cards import cards_text
from .game import Action, Phase, PokerTable
from .table_renderer import render_private_hand
from .web_server import table_url


def table_embed(runtime: object, table: PokerTable, title: str = "Texas Hold'em") -> discord.Embed:
    color = discord.Color.green() if table.hand_running else discord.Color.gold()
    summary = table.table_summary()
    if len(summary) > 700:
        summary = summary[:697] + "..."
    embed = discord.Embed(title=title, description=summary, color=color)
    embed.add_field(name="External table", value=table_url(runtime.config, table), inline=False)
    embed.set_footer(text="Discord is the control interface. Open the table link for the large display.")
    return embed


async def send_error(interaction: discord.Interaction, error: Exception) -> None:
    message = f"Error: {error}"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def publish_table(
    runtime: object,
    interaction: discord.Interaction,
    table: PokerTable,
    message: Optional[str] = None,
) -> None:
    view = LobbyView(runtime, table) if table.phase == Phase.LOBBY else GameActionView(runtime, table)
    if interaction.response.is_done():
        await interaction.followup.send(content=message, embed=table_embed(runtime, table), view=view)
    else:
        await interaction.response.send_message(content=message, embed=table_embed(runtime, table), view=view)


class LobbyView(discord.ui.View):
    def __init__(self, runtime: object, table: PokerTable) -> None:
        super().__init__(timeout=None)
        self.runtime = runtime
        self.table = table
        self.add_item(
            discord.ui.Button(
                label="Open Table",
                style=discord.ButtonStyle.link,
                url=table_url(runtime.config, table),
            )
        )

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            message = self.table.add_player(interaction.user.id, interaction.user.display_name)
            await self.runtime.registry.publish("player.joined", self.table, user_id=interaction.user.id)
            await publish_table(self.runtime, interaction, self.table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            message = self.table.remove_player(interaction.user.id)
            await self.runtime.registry.publish("player.left", self.table, user_id=interaction.user.id)
            await publish_table(self.runtime, interaction, self.table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @discord.ui.button(label="Start Hand", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            self.table.start_hand()
            if self.table.mode == "online":
                await self._send_private_hands(interaction)
            await self.runtime.registry.record_finished_hand_once(self.table)
            await self.runtime.registry.publish("hand.started", self.table)
            await publish_table(self.runtime, interaction, self.table, "Hand started.")
        except Exception as exc:
            await send_error(interaction, exc)

    async def _send_private_hands(self, interaction: discord.Interaction) -> None:
        for player in self.table.players.values():
            if not player.hole:
                continue
            member = interaction.guild.get_member(player.user_id) if interaction.guild else None
            target = member or await interaction.client.fetch_user(player.user_id)
            file = discord.File(render_private_hand(player.hole), filename="your_hand.png")
            embed = discord.Embed(
                title="Your Hole Cards",
                description=cards_text(player.hole),
                color=discord.Color.dark_green(),
            )
            embed.set_image(url="attachment://your_hand.png")
            await target.send(embed=embed, file=file)


class RaiseModal(discord.ui.Modal, title="Raise"):
    total = discord.ui.TextInput(label="Raise total", placeholder="Example: 80")

    def __init__(self, runtime: object, table: PokerTable) -> None:
        super().__init__()
        self.runtime = runtime
        self.table = table

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(str(self.total.value).strip())
            message = self.table.apply_action(interaction.user.id, Action.RAISE_TO, amount)
            await self.runtime.registry.record_finished_hand_once(self.table)
            await self.runtime.registry.publish(
                "hand.action",
                self.table,
                user_id=interaction.user.id,
                action="raise_to",
                amount=amount,
            )
            await publish_table(self.runtime, interaction, self.table, message)
        except Exception as exc:
            await send_error(interaction, exc)


class GameActionView(discord.ui.View):
    def __init__(self, runtime: object, table: PokerTable) -> None:
        super().__init__(timeout=None)
        self.runtime = runtime
        self.table = table
        self.add_item(
            discord.ui.Button(
                label="Open Table",
                style=discord.ButtonStyle.link,
                url=table_url(runtime.config, table),
            )
        )

    async def _act(self, interaction: discord.Interaction, action: Action) -> None:
        try:
            message = self.table.apply_action(interaction.user.id, action)
            await self.runtime.registry.record_finished_hand_once(self.table)
            await self.runtime.registry.publish(
                "hand.action",
                self.table,
                user_id=interaction.user.id,
                action=action.value,
            )
            await publish_table(self.runtime, interaction, self.table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @discord.ui.button(label="Check", style=discord.ButtonStyle.secondary)
    async def check(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._act(interaction, Action.CHECK)

    @discord.ui.button(label="Call", style=discord.ButtonStyle.primary)
    async def call(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._act(interaction, Action.CALL)

    @discord.ui.button(label="Raise", style=discord.ButtonStyle.success)
    async def raise_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.table.current_user_id:
            await send_error(interaction, ValueError("It is not your turn."))
            return
        await interaction.response.send_modal(RaiseModal(self.runtime, self.table))

    @discord.ui.button(label="All-in", style=discord.ButtonStyle.danger)
    async def all_in(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._act(interaction, Action.ALL_IN)

    @discord.ui.button(label="Fold", style=discord.ButtonStyle.danger)
    async def fold(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._act(interaction, Action.FOLD)


class PokerCog(commands.Cog):
    def __init__(self, runtime: object) -> None:
        self.runtime = runtime

    def current_table(self, interaction: discord.Interaction) -> PokerTable:
        return self.runtime.registry.get(interaction.channel_id)

    @app_commands.command(name="poker_online_create", description="Create an online Texas Hold'em table in this channel.")
    @app_commands.describe(small_blind="Small blind", big_blind="Big blind", starting_chips="Initial chips per player")
    async def poker_online_create(
        self,
        interaction: discord.Interaction,
        small_blind: int = 10,
        big_blind: int = 20,
        starting_chips: int = 1000,
    ) -> None:
        try:
            if interaction.channel_id is None:
                raise ValueError("This command must be used in a channel.")
            if small_blind <= 0 or big_blind <= small_blind or starting_chips <= big_blind:
                raise ValueError("Use positive blinds and starting chips greater than the big blind.")
            table = await self.runtime.registry.create_table(
                interaction.channel_id,
                "online",
                small_blind,
                big_blind,
                starting_chips,
            )
            await publish_table(self.runtime, interaction, table, "Online table created.")
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_offline_create", description="Create an offline chip-tracking poker table.")
    @app_commands.describe(small_blind="Small blind", big_blind="Big blind", starting_chips="Initial chips per player")
    async def poker_offline_create(
        self,
        interaction: discord.Interaction,
        small_blind: int = 10,
        big_blind: int = 20,
        starting_chips: int = 1000,
    ) -> None:
        try:
            if interaction.channel_id is None:
                raise ValueError("This command must be used in a channel.")
            if small_blind <= 0 or big_blind <= small_blind or starting_chips <= big_blind:
                raise ValueError("Use positive blinds and starting chips greater than the big blind.")
            table = await self.runtime.registry.create_table(
                interaction.channel_id,
                "offline",
                small_blind,
                big_blind,
                starting_chips,
            )
            await publish_table(self.runtime, interaction, table, "Offline table created. Use Join, then /poker_offline_start.")
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_join", description="Join the current channel's poker table.")
    async def poker_join(self, interaction: discord.Interaction) -> None:
        try:
            table = self.current_table(interaction)
            message = table.add_player(interaction.user.id, interaction.user.display_name)
            await self.runtime.registry.publish("player.joined", table, user_id=interaction.user.id)
            await publish_table(self.runtime, interaction, table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_seat_move", description="Move a seated player to a seat number between hands.")
    @app_commands.describe(player="Player to move", seat="Target seat number, starting from 1")
    async def poker_seat_move(self, interaction: discord.Interaction, player: discord.Member, seat: int) -> None:
        try:
            table = self.current_table(interaction)
            message = table.move_player_to_seat(player.id, seat)
            await self.runtime.registry.publish("seat.moved", table, user_id=player.id, seat=seat)
            await publish_table(self.runtime, interaction, table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_seat_swap", description="Swap two seated players between hands.")
    async def poker_seat_swap(
        self,
        interaction: discord.Interaction,
        first_player: discord.Member,
        second_player: discord.Member,
    ) -> None:
        try:
            table = self.current_table(interaction)
            message = table.swap_seats(first_player.id, second_player.id)
            await self.runtime.registry.publish(
                "seat.swapped",
                table,
                first_user_id=first_player.id,
                second_user_id=second_player.id,
            )
            await publish_table(self.runtime, interaction, table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_offline_start", description="Start an offline hand and post blinds.")
    async def poker_offline_start(self, interaction: discord.Interaction) -> None:
        try:
            table = self.current_table(interaction)
            if table.mode != "offline":
                raise ValueError("This command is only for offline tables.")
            table.start_hand()
            await self.runtime.registry.publish("hand.started", table)
            await publish_table(self.runtime, interaction, table, "Offline hand started.")
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_offline_action", description="Record an offline player's action.")
    @app_commands.describe(player="Player", action="fold/check/call/raise_to/all_in", amount="Raise total, only for raise_to")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="fold", value="fold"),
            app_commands.Choice(name="check", value="check"),
            app_commands.Choice(name="call", value="call"),
            app_commands.Choice(name="raise_to", value="raise_to"),
            app_commands.Choice(name="all_in", value="all_in"),
        ]
    )
    async def poker_offline_action(
        self,
        interaction: discord.Interaction,
        player: discord.Member,
        action: app_commands.Choice[str],
        amount: Optional[int] = None,
    ) -> None:
        try:
            table = self.current_table(interaction)
            if table.mode != "offline":
                raise ValueError("This command is only for offline tables.")
            message = table.apply_action(player.id, Action(action.value), amount)
            await self.runtime.registry.record_finished_hand_once(table)
            await self.runtime.registry.publish(
                "hand.action",
                table,
                user_id=player.id,
                action=action.value,
                amount=amount,
            )
            await publish_table(self.runtime, interaction, table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_offline_board", description="Set the offline 5-card board, e.g. Ah Kd Qs 7c 2h.")
    async def poker_offline_board(self, interaction: discord.Interaction, cards: str) -> None:
        try:
            table = self.current_table(interaction)
            if table.mode != "offline":
                raise ValueError("This command is only for offline tables.")
            message = table.set_offline_board(cards)
            await self.runtime.registry.publish("offline.board_set", table)
            await publish_table(self.runtime, interaction, table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_offline_cards", description="Set one offline player's two cards, e.g. As Ad.")
    async def poker_offline_cards(self, interaction: discord.Interaction, player: discord.Member, cards: str) -> None:
        try:
            table = self.current_table(interaction)
            if table.mode != "offline":
                raise ValueError("This command is only for offline tables.")
            message = table.set_offline_cards(player.id, cards)
            await self.runtime.registry.publish("offline.cards_set", table, user_id=player.id)
            await interaction.response.send_message(message, ephemeral=True)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_offline_showdown", description="Evaluate offline cards and award the pot.")
    async def poker_offline_showdown(self, interaction: discord.Interaction) -> None:
        try:
            table = self.current_table(interaction)
            if table.mode != "offline":
                raise ValueError("This command is only for offline tables.")
            table.finish_showdown()
            await self.runtime.registry.record_finished_hand_once(table)
            await self.runtime.registry.publish("hand.showdown", table)
            await publish_table(self.runtime, interaction, table, "Showdown resolved.")
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_offline_award", description="Manually award the current pot to one winner.")
    async def poker_offline_award(self, interaction: discord.Interaction, winner: discord.Member) -> None:
        try:
            table = self.current_table(interaction)
            if table.mode != "offline":
                raise ValueError("This command is only for offline tables.")
            message = table.manual_award([winner.id])
            await self.runtime.registry.record_finished_hand_once(table)
            await self.runtime.registry.publish("hand.manual_award", table, winner_id=winner.id)
            await publish_table(self.runtime, interaction, table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_status", description="Show the current poker table.")
    async def poker_status(self, interaction: discord.Interaction) -> None:
        try:
            table = self.current_table(interaction)
            await publish_table(self.runtime, interaction, table)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_link", description="Get the external browser table link.")
    async def poker_link(self, interaction: discord.Interaction) -> None:
        try:
            table = self.current_table(interaction)
            await interaction.response.send_message(table_url(self.runtime.config, table))
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_stats", description="Show poker win/loss statistics.")
    async def poker_stats(self, interaction: discord.Interaction) -> None:
        rows = self.runtime.registry.leaderboard()
        if not rows:
            await interaction.response.send_message("No completed hands yet.")
            return
        lines = ["Player | Hands | W/L/P | Net chips", "--- | ---: | --- | ---:"]
        for name, hands, wins, losses, pushes, net in rows:
            lines.append(f"{name} | {hands} | {wins}/{losses}/{pushes} | {net}")
        embed = discord.Embed(title="Poker Stats", description="\n".join(lines), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)


class PokerBot(commands.Bot):
    def __init__(self, runtime: object) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.runtime = runtime

    async def setup_hook(self) -> None:
        await self.add_cog(PokerCog(self.runtime))
        await self.runtime.web_server.start()
        await self.tree.sync()

    async def close(self) -> None:
        await self.runtime.web_server.stop()
        await super().close()


def create_bot(runtime: object) -> PokerBot:
    return PokerBot(runtime)
