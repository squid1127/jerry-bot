"""Database models for Gemini plugin."""

from tortoise import fields, Model

class Channel(Model):
    """Model for a channel."""

    # Identifiers
    channel_id = fields.BigIntField(primary_key=True)
    guild = fields.ForeignKeyField("models.Guild", related_name="channels", on_delete=fields.CASCADE)
    model = fields.ForeignKeyField("models.ModelEntry", related_name="channels", on_delete=fields.SET_NULL, null=True)

    # Provider info
    provider_name = fields.CharField(max_length=255)
    provider_overrides = fields.JSONField(default=dict)
    
    # Prompts and configuration
    prompt = fields.TextField(null=True)
    override_system_prompt = fields.BooleanField(default=False)
    mention_mode = fields.BooleanField(default=False)

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

class ModelEntry(Model):
    """Model for storing provider and model-specific configuration overrides at the channel level."""

    # Identifiers
    id = fields.IntField(pk=True)

    # Model configuration
    model_name = fields.CharField(max_length=255)
    prompt = fields.TextField(null=True)
    temperature = fields.FloatField(null=True)
    max_tokens = fields.IntField(null=True)
    top_p = fields.FloatField(null=True)
    top_k = fields.IntField(null=True)
    overrides = fields.JSONField(default=dict)

    class Meta:  # type: ignore
        """Meta options for ModelEntry."""

        table = "jerry_gemini_model_entries"