"""Utility functions for Discord interactions in the Gemini plugin."""

import discord

class UserFacingException(Exception):
    """Base class for exceptions that should be shown to the user in a friendly way."""
    pass

async def send_ephemeral_response(
    interaction: discord.Interaction,
    error: str | None = None,
    success: str | None = None,
):
    """Helper function to send an ephemeral response to a Discord interaction."""
    if error:
        embed = create_error_embed(description=error)
    elif success:
        embed = create_success_embed(description=success)
    else:
        raise ValueError("Either error or success message must be provided.")
    if interaction.response.is_done():
        return await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        return await interaction.response.send_message(embed=embed, ephemeral=True)


def create_error_embed(description: str, title: str = "Error") -> discord.Embed:
    """Helper function to create a standardized error embed."""
    return discord.Embed(
        title=title + " 🚫", description=description, color=discord.Color.red()
    )


def create_success_embed(description: str, title: str = "Success") -> discord.Embed:
    """Helper function to create a standardized success embed."""
    return discord.Embed(
        title=title + " ✅", description=description, color=discord.Color.green()
    )
