"""Database models for Gemini plugin."""

from tortoise import fields, Model


class Channel(Model):
    """Model for a channel."""

    # Identifiers
    channel_id = fields.BigIntField(primary_key=True)
    guild = fields.ForeignKeyField("models.Guild", related_name="channels", on_delete=fields.CASCADE)

    # Provider info
    provider_name = fields.CharField(max_length=255)
    provider_overrides = fields.JSONField(default=dict)
    
    # Prompts and configuration
    prompt = fields.TextField(null=True)
    override_system_prompt = fields.BooleanField(default=False)

    # Metadata
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:  # type: ignore
        """Meta options for Channel."""

        table = "jerry_gemini_channels"


class Guild(Model):
    """Model for guild-specific configuration."""

    # Identifiers
    guild_id = fields.BigIntField(primary_key=True)
    
    # Configuration
    config_data = fields.JSONField(default=dict)
    trusted = fields.BooleanField(default=False)
    prompt = fields.TextField(null=True)
    
    # Metadata
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:  # type: ignore
        """Meta options for Guild."""

        table = "jerry_gemini_guilds"
