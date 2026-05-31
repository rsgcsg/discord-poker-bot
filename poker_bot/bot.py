from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from .game import PokerTable
from .runtime_types import PokerRuntimeProtocol
from .urls import table_url


logger = logging.getLogger(__name__)


def table_embed(runtime: PokerRuntimeProtocol, table: PokerTable, title: str = "Texas Hold'em") -> discord.Embed:
    color = discord.Color.green() if table.hand_running else discord.Color.gold()
    summary = table.table_summary()
    if len(summary) > 700:
        summary = summary[:697] + "..."
    embed = discord.Embed(title=title, description=summary, color=color)
    embed.add_field(name="Table ID", value=str(table.channel_id), inline=True)
    embed.add_field(name="External table", value=table_url(runtime.config, table), inline=False)
    embed.set_footer(text="Open the Activity, sign in automatically, then join and play inside the app.")
    return embed


def is_unsupported_activity_platform(error: Exception) -> bool:
    return isinstance(error, discord.HTTPException) and getattr(error, "code", None) == 50231


def launch_error_message(runtime: PokerRuntimeProtocol, table: PokerTable | None, error: Exception) -> str:
    if is_unsupported_activity_platform(error):
        message = (
            "Error: this Discord client platform is not enabled for the Poker Activity. "
            "Enable the platform in Discord Developer Portal, or use Discord desktop/web. "
        )
        if table is not None:
            message += f"Browser backup: {table_url(runtime.config, table)}"
        else:
            message += "You can still use the Browser Backup link from a table message."
        return message
    return f"Error: {error}"


async def send_message_fallback(interaction: discord.Interaction, message: str) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
        return
    except (discord.NotFound, discord.HTTPException):
        logger.warning("Interaction response failed; falling back to channel message.", exc_info=True)

    if interaction.channel is not None:
        await interaction.channel.send(f"{interaction.user.mention} {message}")


async def send_error(interaction: discord.Interaction, error: Exception) -> None:
    await send_message_fallback(interaction, f"Error: {error}")


async def launch_activity_for_table(
    runtime: PokerRuntimeProtocol,
    interaction: discord.Interaction,
    table: PokerTable | None = None,
) -> None:
    try:
        if table is not None:
            runtime.web_server.set_launch_target(interaction.user.id, table.channel_id)
        await interaction.response.launch_activity()
    except Exception as exc:
        await send_message_fallback(interaction, launch_error_message(runtime, table, exc))


async def publish_table(
    runtime: PokerRuntimeProtocol,
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
    def __init__(self, runtime: PokerRuntimeProtocol, table: PokerTable) -> None:
        super().__init__(timeout=None)
        self.runtime = runtime
        self.table = table
        self.add_item(
            discord.ui.Button(
                label="Browser Backup",
                style=discord.ButtonStyle.link,
                url=table_url(runtime.config, table),
            )
        )

    @discord.ui.button(label="Open Poker App", style=discord.ButtonStyle.primary)
    async def launch(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await launch_activity_for_table(self.runtime, interaction, self.table)


class PokerCog(commands.Cog):
    def __init__(self, runtime: PokerRuntimeProtocol) -> None:
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
            await publish_table(self.runtime, interaction, table, "Online table created. Launch the Activity, then join inside the app.")
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
            await publish_table(self.runtime, interaction, table, "Offline table created. Launch the Activity, then join inside the app.")
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
        table = None
        try:
            latest_table_id = self.runtime.registry.latest_table_id()
            if latest_table_id is not None:
                table = self.runtime.registry.get(latest_table_id)
        except Exception as exc:
            await send_error(interaction, exc)
            return
        await launch_activity_for_table(self.runtime, interaction, table)

    @app_commands.command(name="poker_open", description="Launch the embedded poker app at a table.")
    @app_commands.describe(table_id="Table ID shown in the create message")
    async def poker_open(self, interaction: discord.Interaction, table_id: str) -> None:
        try:
            table = self.runtime.registry.get_by_public_id(table_id)
        except Exception as exc:
            await send_error(interaction, exc)
            return
        await launch_activity_for_table(self.runtime, interaction, table)

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
    def __init__(self, runtime: PokerRuntimeProtocol) -> None:
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
            logger.info("Skipped global Discord slash command sync.")

    async def close(self) -> None:
        await self.runtime.web_server.stop()
        await super().close()


def create_bot(runtime: PokerRuntimeProtocol) -> PokerBot:
    return PokerBot(runtime)
