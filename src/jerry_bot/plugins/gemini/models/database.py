"""Database models for Gemini plugin."""

from tortoise import fields, Model


class ChannelRecord(Model):
    """Model for a channel."""

    # Identifiers
    channel_id = fields.BigIntField(primary_key=True)
    guild_id = fields.BigIntField()

    # Prompts and configuration
    active = fields.BooleanField(default=True)
    prompt = fields.TextField(null=True)
    override_system_prompt = fields.BooleanField(default=False)
    mention_mode = fields.BooleanField(default=False)

    # Metadata
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:  # type: ignore
        """Meta options for ChannelRecord."""

        table = "jerry_gemini_channels"


class GuildRecord(Model):
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
        """Meta options for GuildRecord."""

        table = "jerry_gemini_guilds"


class LLMProfileRecord(Model):
    """Model for storing provider and model-specific configuration overrides at the channel level."""

    # Identifiers
    id = fields.IntField(pk=True)
    channel_id = fields.BigIntField()
    provider_name = fields.CharField(max_length=255)

    # Model configuration    
    model_name = fields.CharField(max_length=255)
    prompt = fields.TextField(null=True)
    temperature = fields.FloatField(null=True)
    max_tokens = fields.IntField(null=True)
    top_p = fields.FloatField(null=True)
    top_k = fields.IntField(null=True)
    
    overrides = fields.JSONField(default=dict)

    # Multi Profile Support    
    failover_options = fields.JSONField(default=dict)
    
    class Meta:  # type: ignore
        """Meta options for LLMProfileRecord."""

        table = "jerry_gemini_llm_profiles"
