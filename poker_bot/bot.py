from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from .game import PokerTable
from .web_server import table_url


logger = logging.getLogger(__name__)


def table_embed(runtime: object, table: PokerTable, title: str = "Texas Hold'em") -> discord.Embed:
    color = discord.Color.green() if table.hand_running else discord.Color.gold()
    summary = table.table_summary()
    if len(summary) > 700:
        summary = summary[:697] + "..."
    embed = discord.Embed(title=title, description=summary, color=color)
    embed.add_field(name="Table ID", value=str(table.channel_id), inline=True)
    embed.add_field(name="External table", value=table_url(runtime.config, table), inline=False)
    embed.set_footer(text="Discord creates/seats tables only. Play the hand on the website.")
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
    message: str | None = None,
) -> None:
    view = SeatingView(runtime, table)
    if interaction.response.is_done():
        await interaction.followup.send(content=message, embed=table_embed(runtime, table), view=view)
    else:
        await interaction.response.send_message(content=message, embed=table_embed(runtime, table), view=view)


class SeatingView(discord.ui.View):
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
            await interaction.followup.send(
                f"Joined. Open the table and log in with Discord: {table_url(self.runtime.config, self.table)}",
                ephemeral=True,
            )
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


class PokerCog(commands.Cog):
    def __init__(self, runtime: object) -> None:
        self.runtime = runtime

    @app_commands.command(name="poker_online_create", description="Create an online Texas Hold'em table.")
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
            await publish_table(self.runtime, interaction, table, "Online table created. Use the website to play.")
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
            await publish_table(self.runtime, interaction, table, "Offline table created. Use the website to run the hand.")
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_join", description="Join a poker table by table id.")
    @app_commands.describe(table_id="Table ID shown in the create message")
    async def poker_join(self, interaction: discord.Interaction, table_id: str) -> None:
        try:
            table = self.runtime.registry.get_by_public_id(table_id)
            message = table.add_player(interaction.user.id, interaction.user.display_name)
            await self.runtime.registry.publish("player.joined", table, user_id=interaction.user.id)
            await publish_table(self.runtime, interaction, table, message)
            await interaction.followup.send(
                f"Joined. Open the table and log in with Discord: {table_url(self.runtime.config, table)}",
                ephemeral=True,
            )
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_leave", description="Leave a poker table by table id.")
    @app_commands.describe(table_id="Table ID shown in the create message")
    async def poker_leave(self, interaction: discord.Interaction, table_id: str) -> None:
        try:
            table = self.runtime.registry.get_by_public_id(table_id)
            message = table.remove_player(interaction.user.id)
            await self.runtime.registry.publish("player.left", table, user_id=interaction.user.id)
            await publish_table(self.runtime, interaction, table, message)
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_link", description="Get an external browser table link.")
    @app_commands.describe(table_id="Table ID shown in the create message")
    async def poker_link(self, interaction: discord.Interaction, table_id: str) -> None:
        try:
            table = self.runtime.registry.get_by_public_id(table_id)
            await interaction.response.send_message(table_url(self.runtime.config, table))
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_launch", description="Launch the embedded poker app in Discord.")
    async def poker_launch(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.launch_activity()
        except Exception as exc:
            await send_error(interaction, exc)

    @app_commands.command(name="poker_tables", description="List live poker tables.")
    async def poker_tables(self, interaction: discord.Interaction) -> None:
        tables = self.runtime.registry.tables()
        if not tables:
            await interaction.response.send_message("No live poker tables.")
            return
        lines = [
            f"{table.channel_id}: {table.mode}, {len(table.players)} players, {table.phase.value}, {table_url(self.runtime.config, table)}"
            for table in tables
        ]
        await interaction.response.send_message("\n".join(lines))

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
        if self.runtime.config.discord_guild_id:
            guild = discord.Object(id=self.runtime.config.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            commands = await self.tree.sync(guild=guild)
            logger.info(
                "Synced %s Discord slash commands to guild %s",
                len(commands),
                self.runtime.config.discord_guild_id,
            )
        else:
            commands = await self.tree.sync()
            logger.info("Synced %s global Discord slash commands", len(commands))

    async def close(self) -> None:
        await self.runtime.web_server.stop()
        await super().close()


def create_bot(runtime: object) -> PokerBot:
    return PokerBot(runtime)
