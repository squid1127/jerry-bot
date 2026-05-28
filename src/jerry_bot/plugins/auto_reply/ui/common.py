"""Common methods for Auto Reply UI"""

import discord


async def send_error(
    interaction: discord.Interaction, title: str, description: str
) -> None:
    """Central helper to send an ephemeral error message to the user."""
    if not interaction.response.is_done():
        await interaction.response.send_message(
            embed=discord.Embed(
                title=title, description=description, color=discord.Color.red()
            ),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            embed=discord.Embed(
                title=title, description=description, color=discord.Color.red()
            ),
            ephemeral=True,
        )
