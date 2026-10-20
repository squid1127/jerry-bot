"""Configuration models for the Joe plugin."""

from pydantic import BaseModel, Field


class JoePluginConfig(BaseModel):
    """Configuration model for the Joe plugin."""

    enabled: bool = Field(
        default=False, description="Whether the Joe plugin is enabled."
    )
    entries: dict[int, dict[int,str]] = Field(
        default_factory=dict,
        description="Mapping of user ids to a mapping of channel ids to their respective names",
    )

    retry_period: float = Field(
        86400,
        description="The time between messages to ignore incoming messages in the event of a permissions error"
    )