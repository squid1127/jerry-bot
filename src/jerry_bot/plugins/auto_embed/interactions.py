"""Discord UIs, etc for AutoEmbed plugin."""

import discord


def build_embed(content: dict) -> discord.Embed | None:
    """Build a Discord embed from a dictionary."""
    try:
        embed = discord.Embed.from_dict(content)
    except Exception:
        return None
    return embed


def parse_color(color_input: str) -> int | None:
    """Parse a color string into a Discord color integer.
    
    Accepts:
    - Hex codes: #FF5733 or FF5733
    - Color names: blue, red, green, gold, etc.
    - Decimal integers as strings
    
    Returns the color as an integer, or None if parsing fails.
    """
    if not color_input or not color_input.strip():
        return None
    
    color_input = color_input.strip().lower()
    
    # Try hex code
    if color_input.startswith("#"):
        color_input = color_input[1:]
    if len(color_input) == 6 and all(c in "0123456789abcdef" for c in color_input):
        try:
            return int(color_input, 16)
        except ValueError:
            return None
    
    # Try predefined color names
    color_map = {
        "blue": discord.Color.blue().value,
        "red": discord.Color.red().value,
        "green": discord.Color.green().value,
        "gold": discord.Color.gold().value,
        "purple": discord.Color.purple().value,
        "orange": discord.Color.orange().value,
        "pink": discord.Color.magenta().value,
        "magenta": discord.Color.magenta().value,
        "teal": discord.Color.teal().value,
        "blurple": discord.Color.blurple().value,
        "yellow": discord.Color.yellow().value,
        "dark_red": discord.Color.dark_red().value,
        "dark_green": discord.Color.dark_green().value,
        "dark_blue": discord.Color.dark_blue().value,
        "dark_magenta": discord.Color.dark_magenta().value,
        "dark_teal": discord.Color.dark_teal().value,
        "darker_gray": discord.Color.darker_gray().value,
        "dark_gray": discord.Color.dark_gray().value,
        "light_gray": discord.Color.light_gray().value,
        "lighter_gray": discord.Color.lighter_gray().value,
    }
    
    if color_input in color_map:
        return color_map[color_input]
    
    # Try parsing as decimal integer
    try:
        return int(color_input)
    except ValueError:
        return None


async def preview_embed(
    interaction: discord.Interaction,
    embed: discord.Embed,
    message: str | None = None,
) -> None:
    """Preview an embed to the user."""
    view = AutoEmbedPreviewView(embed, message, interaction)
    await interaction.response.send_message(
        embeds=[discord.Embed(title="Embed Preview", color=discord.Color.blue()), embed],
        view=view,
        ephemeral=True,
    )


class AutoEmbedInputForm(discord.ui.Modal):
    """Modal form for AutoEmbed input."""

    def __init__(self) -> None:
        super().__init__(title="AutoEmbed Input Form", timeout=600.0)  # 10 minute timeout

        # Inputs
        self.input_message = discord.ui.TextInput(
            label="Plaintext Message (Optional)",
            style=discord.TextStyle.paragraph,
            placeholder="Plain text message to include above the embed.",
            required=False,
            max_length=2000,
        )
        self.add_item(self.input_message)

        self.input_title = discord.ui.TextInput(
            label="Embed Title",
            style=discord.TextStyle.short,
            placeholder="Title text for the embed.",
            required=False,
            max_length=256,
        )
        self.add_item(self.input_title)

        self.input_description = discord.ui.TextInput(
            label="Embed Description",
            style=discord.TextStyle.paragraph,
            placeholder="Description text for the embed.",
            required=False,
            max_length=4000,
        )
        self.add_item(self.input_description)

        self.input_color = discord.ui.TextInput(
            label="Color (Optional)",
            style=discord.TextStyle.short,
            placeholder="Hex code (e.g., #FF5733) or color name (e.g., blue, red).",
            required=False,
            max_length=20,
        )
        self.add_item(self.input_color)
        
        self.input_yaml = discord.ui.TextInput(
            label="YAML Overrides (Optional)",
            style=discord.TextStyle.paragraph,
            placeholder="# YAML formatted embed overrides.",
            required=False,
            max_length=4000,
        )
        self.add_item(self.input_yaml)
        
    def export_dict(self) -> dict:
        """Export form data to a dictionary."""
        if not self.input_title.value and not self.input_description.value and not self.input_yaml.value.strip():
            raise ValueError("At least one of title, description, or YAML overrides must be provided.")
        
        data = {
            "title": self.input_title.value,
            "description": self.input_description.value,
        }
        
        # Add color if provided
        if self.input_color.value.strip():
            color_value = parse_color(self.input_color.value)
            if color_value is not None:
                data["color"] = color_value
        
        # Merge YAML overrides if provided
        if self.input_yaml.value.strip():
            import yaml

            try:
                yaml_data = yaml.safe_load(self.input_yaml.value)
                if isinstance(yaml_data, dict):
                    data.update(yaml_data)
            except yaml.YAMLError:
                pass  # Ignore YAML errors for now
        return data

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle form submission."""
        try:
            content_dict = self.export_dict()
            embed = build_embed(content_dict)
            if embed is None:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        description="Failed to build embed from provided data.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
            await preview_embed(interaction, embed, self.input_message.value or None)
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"An unexpected error occurred: {e}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

    async def on_timeout(self) -> None:
        """Handle modal timeout gracefully."""
        # Modal timeout means the user didn't submit in time.
        # We can't send a response since the interaction has expired.
        # Just silently timeout to avoid "interaction failed" errors.
        pass


class AutoEmbedPreviewView(discord.ui.View):
    """View for previewing AutoEmbed."""

    def __init__(self, embed: discord.Embed, message: str | None = None, interaction: discord.Interaction | None = None) -> None:
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.embed = embed
        self.message = message
        self.interaction = interaction

    @discord.ui.button(label="Send ➡️", style=discord.ButtonStyle.green)
    async def send_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle send button click."""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.channel.send(content=self.message, embed=self.embed)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="I don't have permission to send messages in this channel.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"An unexpected error occurred while sending the embed: {e}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=discord.Embed(description="Embed sent!", color=discord.Color.green()),
            ephemeral=True,
        )
        
    @discord.ui.button(label="Interaction Mode", style=discord.ButtonStyle.secondary)
    async def interaction_mode_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle interaction mode button click."""
        try:
            # Send using an interaction followup
            await interaction.response.send_message(content=self.message, embed=self.embed)
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"Uh oh! I tried to send something but it blew up: :(",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

    async def on_timeout(self) -> None:
        """Handle view timeout gracefully."""
        # Disable all buttons when the view times out
        for item in self.children:
            item.disabled = True
            
        if self.interaction:
            try:
                await self.interaction.edit_original_response(view=self)
            except Exception:
                pass  # Ignore errors on timeout edit